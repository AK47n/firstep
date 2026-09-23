# -*- coding: utf-8 -*-
"""「我的器件」的端点（工单 hwcheck-unknown-device/02）。

HTTP 层判据（域层判据在 `tests/test_my_devices.py`）：

① 三件事的端点都在：列出 / 新增（按 id 幂等更新）/ 删除；
② **id 撞库内 slug → 400 中文当场点名要求改名**（不静默加后缀）；
③ 落点 = 配置目录下的 `hwcheck_devices/`（**不是**模块库 / 母版库那两个目录）；
④ 提前把自建件当器件发给检测计划**不许 400**——这一版它还不是模块（工单 03
   才接进渲染），页面能勾、能看，但生成链上游的「库外 slug 大声失败」这条守卫
   一个字都不许松。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contest_generator.hwcheck_triage import triage_context_text
from contest_generator.my_devices import (
    DEVICE_JSON,
    MY_DEVICES_DIRNAME,
    CustomDevice,
    my_devices_dir,
    save_device,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from tests._c_escape import decode_c_string

DEVICE_BODY = {
    "id": "mine_gyro",
    "name": "卖家给的六轴模块",
    "bus": "i2c",
    "address": 0x68,
    "register": 0x75,
    "expect": 0x68,
    "notes": "卖家页写的 WHO_AM_I",
}


@pytest.fixture()
def devices_client(tmp_path):
    """真库 + 空数据目录的 TestClient：数据目录 = `<tmp>/data/`（配置目录）。

    用**真模块库**：`known_slugs` 那条载荷判据要真库的 slug 集（`i2c_probe` /
    `oled` …），页面据此在**提交之前**拦住撞名的 id。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    repo = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ctx = AppContext(
        config_path=data_dir / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: FakeLLM(),
    )
    return TestClient(create_app(ctx)), data_dir


@pytest.fixture()
def clash_client(tmp_path):
    """库里真有一个叫 `mine_gyro` 的模块 + 空数据目录 —— 造一次**真撞名**。

    为什么要刻意造：这是个**双保险**判据（页面按 `known_slugs` 提前拦、服务端
    照旧拒），而库里 96 个 slug 一个都不以 `mine_` 开头——不造一个，服务端那条
    腿就靠"恰好没人撞得上"过关，是个摆设。撞名一旦发生，静默加后缀是最坏的
    解法（学生填 `mine_gyro`、页面存成 `mine_gyro_2`，过两天照原名找就找不到）。
    """
    import json

    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    library = tmp_path / "modules"
    (library / "mine_gyro").mkdir(parents=True)
    (library / "mine_gyro" / "manifest.json").write_text(
        json.dumps(
            {"slug": "mine_gyro", "description": "库里真有一个同名的模块", "platforms": {}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ctx = AppContext(
        config_path=data_dir / "config.json",
        config=AppConfig(
            api_key="sk-test", module_library_dir=library, masters_dir=tmp_path / "masters"
        ),
        llm_factory=lambda config: FakeLLM(),
    )
    return TestClient(create_app(ctx)), data_dir


# ---------------------------------------------------------------------------
# 列出
# ---------------------------------------------------------------------------


def test_list_is_empty_when_nothing_was_created_yet(devices_client):
    """"一件都没建过"是正常状态（200 + 空列表），不是错误。"""
    client, _ = devices_client
    response = client.get("/api/my-devices")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["devices"] == []
    assert body["known_slugs"], "载荷要带库内 slug 集（页面据此当场拦住撞名的 id）"


def test_list_projects_facts_plus_derived_address_forms(devices_client):
    """载荷 = 存下来的事实 + 派生的 8 位读 / 写形式（页面双向显示用）。"""
    client, _ = devices_client
    assert client.post("/api/my-devices", json={"device": DEVICE_BODY}).status_code == 200
    body = client.get("/api/my-devices").json()
    assert len(body["devices"]) == 1
    device = body["devices"][0]
    assert device["id"] == "mine_gyro"
    assert device["address"] == 0x68
    assert device["address_forms"] == {
        "address7": "0x68", "read8": "0xD1", "write8": "0xD0",
    }
    assert device["bus_label"] == "I2C"
    assert "platform" not in device, "件与平台无关：定义里没有平台"


# ---------------------------------------------------------------------------
# 新增 / 更新（按 id 幂等）
# ---------------------------------------------------------------------------


def test_create_then_update_by_id_is_idempotent(devices_client):
    """同一 id 再存一次 = 更新那一件（不新建第二份），`created_at` 不动。"""
    client, data_dir = devices_client
    first = client.post("/api/my-devices", json={"device": DEVICE_BODY}).json()
    second = client.post(
        "/api/my-devices",
        json={"device": {**DEVICE_BODY, "name": "改过的名字"}},
    ).json()
    assert second["device"]["name"] == "改过的名字"
    assert second["device"]["created_at"] == first["device"]["created_at"]
    assert len(client.get("/api/my-devices").json()["devices"]) == 1
    # 落点：配置目录下的 hwcheck_devices/<id>/device.json
    entry = my_devices_dir(data_dir) / "mine_gyro"
    assert entry == data_dir / MY_DEVICES_DIRNAME / "mine_gyro"
    assert (entry / DEVICE_JSON).is_file()
    assert (entry / "materials").is_dir(), "资料副本目录先预留出来（工单 07 用）"


def test_create_returns_the_saved_device(devices_client):
    client, _ = devices_client
    body = client.post("/api/my-devices", json={"device": DEVICE_BODY}).json()
    assert body["ok"] is True
    assert body["device"]["id"] == "mine_gyro"
    assert body["device"]["created_at"], "时间戳由服务端写（页面不编时间）"


def test_create_rejects_a_bad_address_with_the_seven_bit_hint(devices_client):
    """手册里 0xD0 那种 8 位写法 → 400 中文点明"请填 7 位形式"。"""
    client, _ = devices_client
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "address": 0xD0}}
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "7 位" in detail and "0x68" in detail


def test_create_rejects_missing_address_for_i2c(devices_client):
    client, _ = devices_client
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "address": None}}
    )
    assert response.status_code == 400
    assert "地址" in response.json()["detail"]


def test_create_rejects_expect_without_register(devices_client):
    client, _ = devices_client
    response = client.post(
        "/api/my-devices",
        json={"device": {**DEVICE_BODY, "register": None, "expect": 0x68}},
    )
    assert response.status_code == 400
    assert "寄存器" in response.json()["detail"]


def test_create_rejects_an_unknown_bus_with_the_vocabulary(devices_client):
    client, _ = devices_client
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "bus": "can"}}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "can" in detail and "i2c" in detail


def test_create_rejects_a_non_i2c_device_that_fills_an_address(devices_client):
    client, _ = devices_client
    response = client.post(
        "/api/my-devices",
        json={"device": {**DEVICE_BODY, "bus": "spi"}},
    )
    assert response.status_code == 400
    assert "i2c" in response.json()["detail"]


def test_create_rejects_a_missing_device_object(devices_client):
    """载荷形状非法 → 400 中文（不裸 500）。"""
    client, _ = devices_client
    response = client.post("/api/my-devices", json={})
    assert response.status_code == 400
    assert "device" in response.json()["detail"]


@pytest.mark.parametrize(
    "bad_id", ["gyro", "mine gyro", "mine_", "mine/../evil", "mine_gyro-2", "mine_gy-ro"]
)
def test_create_rejects_an_id_outside_the_device_grammar(devices_client, bad_id):
    client, _ = devices_client
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "id": bad_id}}
    )
    assert response.status_code == 400, response.text
    assert "mine_" in response.json()["detail"]


def test_create_rejects_a_hyphen_id_and_says_why(devices_client):
    """工单 12 的**建件入口**：连字符 id 必须 400，且说清为什么（拼进 C 函数名）。

    `02` 定的 id 文法允许 `-`，而 `03` 把 id 原样拼进 C 函数名——`mine_gyro-2`
    造出的检测工程里是 `static void hwcheck_custom_mine_gyro-2(void)`，不是合法
    C 标识符，整份工程编不过（现场与量具：`probe-12-hyphen-id.py`）。
    """
    client, data_dir = devices_client
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "id": "mine_gyro-2"}}
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "连字符" in detail, detail
    assert not (my_devices_dir(data_dir) / "mine_gyro-2").exists(), "不许静默存下"


def test_a_stale_hyphen_entry_is_named_loudly_and_never_reaches_a_project(
    generate_client, tmp_path
):
    """工单 12 的**预览 / 生成入口**：盘上已有的坏 id（旧条目）大声拦下，不落工程。

    收紧文法之前建的条目还躺在数据目录里（目录名 = id = `mine_gyro-2`）。
    列表、预览、生成三个入口都要 400 点名；**生成绝不落盘**——缺陷现场是
    「三个端点全 200、坏工程已经写进磁盘」，这条按同一个量具反向钉。
    """
    client, data_dir = generate_client
    root = my_devices_dir(data_dir)
    entry = root / "mine_gyro-2"
    (entry / "materials").mkdir(parents=True)
    (entry / DEVICE_JSON).write_text(
        json.dumps(
            {"id": "mine_gyro-2", "name": "旧条目", "bus": "i2c", "address": 0x68}
        ),
        encoding="utf-8",
    )
    listed = client.get("/api/my-devices")
    assert listed.status_code == 400, listed.text
    assert "mine_gyro-2" in listed.json()["detail"]

    request = {
        "platform": PLATFORM_STM32,
        "debug_uart": True,
        "oled": False,
        "devices": ["mine_gyro-2"],
    }
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    preview = client.post("/api/hwcheck/preview", json=request)
    assert preview.status_code == 400, preview.text
    assert "mine_gyro-2" in preview.json()["detail"]
    generated = client.post(
        "/api/hwcheck/generate", json={**request, "parent_dir": str(output_parent)}
    )
    assert generated.status_code == 400, generated.text
    assert list(output_parent.iterdir()) == [], "坏工程一个目录都不该落"


# ---------------------------------------------------------------------------
# 与库内 slug 的冲突：400 点名要求改名（本单的反证靶子）
# ---------------------------------------------------------------------------


def test_id_clashing_with_a_library_slug_is_400_and_names_the_id(clash_client):
    """**反证靶子**：撞库内 slug 必须 400 点名，不能静默加后缀、也不能默默存下。

    静默加后缀是最坏的解法：学生填 `mine_gyro`、页面存成 `mine_gyro_2`，
    过两天他照 `mine_gyro` 找这件东西就找不到了。
    """
    client, data_dir = clash_client
    response = client.post("/api/my-devices", json={"device": DEVICE_BODY})
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "mine_gyro" in detail
    assert "改名" in detail
    assert "库内" in detail
    # 没有静默加后缀：那个 id 名下什么都不该被建出来
    assert not (my_devices_dir(data_dir) / "mine_gyro").exists()
    assert client.get("/api/my-devices").json()["devices"] == []


def test_the_clash_judgement_reads_the_library_at_request_time(clash_client):
    """撞名判据吃的是**当下的**库（不是一份写死的名单）：库里换成别的 slug，
    `known_slugs` 跟着变。"""
    client, _ = clash_client
    known = client.get("/api/my-devices").json()["known_slugs"]
    assert known == ["mine_gyro"]
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "id": "mine_led"}}
    )
    assert response.status_code == 200, "库里没有 mine_led，就该能存"


def test_library_slugs_never_take_the_mine_prefix(devices_client):
    """真库里一个 `mine_` 开头的 slug 都没有（前缀就是两类东西的分界）。

    这条是**事实**、不是守卫：它保证了 `known_slugs` 与自建件 id 正常不重叠，
    页面提前拦那一下在真库上是"永远不触发"的安全网。哪天真有个 `mine_*` 模块
    入库，撞名判据（服务端那条腿）照样兜得住——见上面 clash_client 那组。
    """
    client, _ = devices_client
    known = client.get("/api/my-devices").json()["known_slugs"]
    assert known, "真库应读得到 slug"
    assert [slug for slug in known if slug.startswith("mine_")] == []


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


def test_delete_removes_the_entry_and_its_materials(devices_client):
    client, data_dir = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    entry = my_devices_dir(data_dir) / "mine_gyro"
    (entry / "materials" / "manual.pdf").write_bytes(b"%PDF-1.4 fake")
    response = client.delete("/api/my-devices/mine_gyro")
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert not entry.exists(), "连同资料副本一起删（不留下孤儿目录）"
    assert client.get("/api/my-devices").json()["devices"] == []


def test_delete_unknown_id_is_400_chinese(devices_client):
    client, _ = devices_client
    response = client.delete("/api/my-devices/mine_nope")
    assert response.status_code == 400, response.text
    assert "mine_nope" in response.json()["detail"]


def test_delete_is_idempotent_after_the_first_success(devices_client):
    """第二次删同一条 = 400 点名（不静默 200：页面据此知道该刷新列表了）。"""
    client, _ = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    assert client.delete("/api/my-devices/mine_gyro").status_code == 200
    assert client.delete("/api/my-devices/mine_gyro").status_code == 400


@pytest.mark.anyio
async def test_delete_cannot_walk_out_of_the_data_dir(devices_client):
    """删除端点的 id 必须过文法——**这条是路径穿越的正面防线**。

    两种打法在这一层各是什么下场（都用**原始 ASGI 路径**打，绕开 httpx 的 URL
    规范化——`TestClient.delete("/api/my-devices/..")` 会被客户端先归一成
    `/api/`，请求根本到不了这个路由；本单实测：那样写用例照样绿，但绿得毫无意义）：

    * 字面 `..` 段：Starlette 的路由在匹配前就把它当不合法路径（404）——防线在
      框架层，不在我们这儿；
    * **百分号编码**的 `%2e%2e`：路由段 `{device_id}` 照收，解码后就是 `..`，一路
      落到 `delete_device` → `Path(root) / ".."` = 配置目录（装着 config.json）→
      `rmtree`。**这条在本单修复前是打得通的**（域层用例
      `test_delete_and_load_refuse_ids_outside_the_entry_grammar` 逐字证过：
      `delete_device(root, "..")` 会删掉配置目录）。

    判据因此落在**拼接 id 的那一层**（域层 `_entry_dir`）：路由或框架的路径语法
    拦不住编码变体，"每个调用方都记得先校验"是迟早会漏的口头约定。
    """
    import httpx

    client, data_dir = devices_client
    (data_dir / "config.json").write_text("{}", encoding="utf-8")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=client.app), base_url="http://t"
    ) as raw:
        encoded = await raw.request(
            "DELETE", "http://t/api/my-devices/%2e%2e",
            extensions={"path": "/api/my-devices/%2e%2e"},
        )
        literal = await raw.request(
            "DELETE", "http://t/api/my-devices/..",
            extensions={"path": "/api/my-devices/.."},
        )

    assert encoded.status_code == 400, encoded.text
    assert "mine_" in encoded.json()["detail"], encoded.json()
    assert literal.status_code == 404, literal.text
    assert (data_dir / "config.json").is_file(), "配置目录不该被动到"
    assert data_dir.is_dir()


# ---------------------------------------------------------------------------
# 自建件进检测计划：**02 只让它"能被选"，03 起它真的產出探测小节**
# ---------------------------------------------------------------------------


def test_passing_a_custom_device_id_as_a_device_does_not_400(devices_client):
    """自建件出现在请求里不该让整次预览 400（页面已经能勾它了）。

    工单 02 时它只是"被记下"（不进模块集、不进产物）；**工单 03 起它真的出
    探测小节**——所以这里断言的是"不 400 + 回显 + 真出了它的小节"，而
    "它不是模块、不许当 slug 解析"那条守卫由下面的对照组盯着。
    """
    client, _ = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["mine_gyro"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["devices"] == ["mine_gyro"], "选择要回显（页面据此画 chip）"
    assert "hwcheck_custom_mine_gyro" in body["main_c"], (
        "自建件的探测小节要真的进 main.c（工单 03）：\n" + body["main_c"][:400]
    )
    assert "0x68" in body["main_c"], "ping 的是它自己的地址"


def test_the_probe_module_rides_along_with_a_custom_device(devices_client, tmp_path):
    """有自建件 → 模块集**自动带上 `i2c_probe`**（探测代码要调它的接口）。"""
    client, _ = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["mine_gyro"]},
    ).json()
    assert 'i2c_probe_stm32.h' in body["main_c"], "要 include 该平台的头"
    # 页面载荷里也如实说这一趟测了它（工单 05 的接线说明会用同一份）
    assert [item["slug"] for item in body["custom"]] == ["mine_gyro"]
    assert body["custom"][0]["plan"], "三档文案要下发（页面不另写一份）"
    # 接线那一行（工单 05）：名称 + 地址 + 支点声明的那对脚，脚与接线表逐字同源
    entry = body["custom"][0]
    assert entry["probes"] is True
    rows = [
        row for row in body["wiring"]["rows"] if row["slug"] == "i2c_probe"
    ]
    assert entry["wiring_text"].endswith(
        "、".join(f"{row['role']} → {row['pin']}" for row in rows)
    ), entry["wiring_text"]
    # 顺序表（工单 05）：自建件接在库内排序之后（库内那几件一个不动）
    order = [item["slug"] for item in body["wiring"]["order"]]
    assert order[-1] == "mine_gyro", order
    assert body["wiring"]["order"][-1]["custom"] is True


def test_the_checklist_carries_the_custom_device_classes(generate_client, tmp_path):
    """上板清单（工单 05 验收第 2 条）：自建件三类各一条，端点逐条给出来。"""
    client, _ = generate_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    parent = tmp_path / "out"
    parent.mkdir()
    body = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["mine_gyro"], "parent_dir": str(parent)},
    ).json()
    ids = [item["id"] for item in body["checklist"]]
    for tail in ("answered", "mismatch", "silent"):
        assert f"custom-mine_gyro-{tail}" in ids, ids
    assert "reset" in ids and ids.index("custom-mine_gyro-answered") < ids.index("reset")
    # 每一条都是"应看到什么 / 不对先查哪里"两栏（前端照这个形状渲染）
    for item in body["checklist"]:
        assert item["expect"] and item["check"], item
    # 回读端点给同一份清单（刷新回显的服务端真源）
    back = client.get(
        "/api/hwcheck/project", params={"output_dir": body["output_dir"]}
    ).json()
    assert back["checklist"] == body["checklist"]


@pytest.fixture()
def generate_client(tmp_path):
    """能**真的生成**一份工程的 TestClient：真模块库 + **真母版**，输出落 tmp。

    为什么生成那两条用例不能复用 `devices_client`：那个夹具的 `masters_dir` 是空的
    （预览只要库、不要母版），而生成要复制真母版工程——空母版目录会 400。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    repo = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ctx = AppContext(
        config_path=data_dir / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=repo / "library" / "masters",
        ),
        llm_factory=lambda config: FakeLLM(),
    )
    return TestClient(create_app(ctx)), data_dir


def test_generate_with_a_custom_device_is_not_a_400(generate_client, tmp_path):
    """**预览 200 → 生成 400 那个缺陷的回归判据**（评审抓到的真缺陷）。

    生成端点原先吃 `hwcheck_modules(config)`——那个集合含 `mine_*`，于是自建件被
    当成模块送进生成链、在 `resolve_dependencies` 那里抛「库中不存在模块」；
    而预览走视图的局部 manifests，所以**预览照样 200**。同一条判据两处各算一遍
    就是这个下场（`tests/test_hwcheck.py` 有一条"预览 200 / 生成 400 不许分家"
    的既有判据正是要灭这类事）。
    """
    from contest_generator.context_manifest import read_context_fields

    client, _ = generate_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32,
            "debug_uart": True,
            "oled": False,
            "devices": ["mine_gyro"],
            "parent_dir": str(output_parent),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    project = Path(body["output_dir"])
    assert "hwcheck_custom_mine_gyro" in body["main_c"], "自建件小节要真的进工程"
    assert "i2c_probe" in body["modules"], (
        "支点模块要真进工程（它不在的话 main.c 调的函数无处可寻）：" + repr(body["modules"])
    )
    # 落盘的工程里真有那一节（不只看响应体）
    assert "hwcheck_custom_mine_gyro" in (project / "main.c").read_text(encoding="utf-8")
    fields = read_context_fields(project)
    assert fields is not None and "i2c_probe" in fields["slugs"], fields
    assert "mine_gyro" not in fields["slugs"], "自建件不是模块，不许进 slugs"
    assert fields["devices"] == ["mine_gyro"], "但器件选择要记进清单（回读要用）"


def test_generate_on_mspm0_keeps_the_i2c_instance_alive(generate_client, tmp_path):
    """**mspm0 上真的生成一份带探测小节的工程**（工单 04 的端点面）。

    与 stm32 那一格（上一条）的分工：stm32 的探测走模块自己那组引脚宏，mspm0 的
    探测走**母版 SysConfig 的 `I2C_0` 实例**——而实例的裁剪判据是"消费者 ∩ 选中
    集"。生成链里真正被选中进工程的 slug 集是 `view.generation_slugs`（自建件已
    摘、`i2c_probe` 已补），所以这一格判的是**落盘产物**：裁剪后的 `mspm0.syscfg`
    里 `I2C_0` 的 `$assign` 还在、SysConfig 生成的 `I2C_0_INST` 还在。

    没有它 `i2c_probe.c` 直接编不过（01 的反证项实测过那条链）——但那条链此前
    只在"单独选 `i2c_probe`"的形态上证过；**带自建件的那条路**是这一单新开的，
    少一个 slug 就整格塌掉，所以判据落在这里而不是靠编译探针兜。
    """
    client, _ = generate_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    output_parent = tmp_path / "out-mspm0"
    output_parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_MSPM0,
            "debug_uart": True,
            "oled": False,
            "devices": ["mine_gyro"],
            "parent_dir": str(output_parent),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    project = Path(body["output_dir"])
    assert "hwcheck_custom_mine_gyro" in body["main_c"], "自建件小节要真的进工程"
    assert 'i2c_probe.h' in body["main_c"], (
        "mspm0 侧的头是 `i2c_probe.h`（两平台不同名）：\n" + body["main_c"][:400]
    )
    assert "DL_I2C" not in body["main_c"], (
        "`main.c` 一个字都不许直接调 SDK（母版没有 .h，写进 main.c 会被门禁判"
        "未定义）——`DL_*` 全部封在 `i2c_probe.c` 里：\n" + body["main_c"][:400]
    )
    syscfg = (project / "mspm0.syscfg").read_text(encoding="utf-8")
    assert 'I2C_0.peripheral.sdaPin.$assign = "PA0";' in syscfg, (
        "带自建件这一路也要让 I2C_0 活下来（消费者 ∩ 选中集）"
    )
    assert 'I2C_0.peripheral.sclPin.$assign = "PA1";' in syscfg, syscfg[:200]
    # `I2C_0_INST` 本体（`Debug/ti_msp_dl_config.h`）是 **SysConfig CLI 在编译
    # 那一步**生成的，不是生成端点产出的：生成端点只负责把 Debug/makefile 摆好
    # （编译链的入口）。所以这里判到 makefile 为止，`I2C_0_INST` 那条判据归真编译
    # 探针（`check_mspm0`，它跑在 gmake 之后）——两处各判各的，不越界。
    assert (project / "Debug" / "makefile").is_file(), (
        "编译链入口（Debug/makefile）要摆好，否则这一份工程在检测页点不动「编译」"
    )


def test_preview_and_generate_render_byte_identical_main_c(generate_client, tmp_path):
    """票面验收线：**两处产物逐字节一致**（注入点在 main.c 的唯一产地）。

    这是工单第 6 条的**行为**判据（源码正则判据在
    `tests/test_hwcheck_custom.py::test_preview_and_generate_share_the_same_render_source`
    ——那条只挡"谁又自己拼了一份"，证不了两次渲染真的同字节）。
    """
    client, _ = generate_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    request = {
        "platform": PLATFORM_STM32,
        "debug_uart": True,
        "oled": True,
        "devices": ["mine_gyro"],
    }
    preview = client.post("/api/hwcheck/preview", json=request).json()
    generated = client.post(
        "/api/hwcheck/generate", json={**request, "parent_dir": str(output_parent)}
    ).json()
    assert preview["main_c"] == generated["main_c"], (
        "预览与生成必须逐字节相同（同一份渲染、同一处注入）"
    )
    assert preview["main_c"] == (
        Path(generated["output_dir"]) / "main.c"
    ).read_text(encoding="utf-8"), "落盘的那份也要一样"


def test_a_non_i2c_custom_device_still_does_not_render_a_probe(devices_client):
    """非 I2C 的库外件：这一版**不生成探测程序**（清单与排障是工单 05 的事）。

    工单 05 起 `custom` 这一栏的语义是**检测页计划**（选中的每一件都在，含不出
    小节的），所以判据从"载荷里空数组"改成"这一件在，但 `probes=False`"——那才是
    页面说得出"为什么不给它出探测程序"的前提（见
    `tests/test_hwcheck_custom.py::test_the_page_payload_carries_the_plan_for_every_selected_custom_device`）。
    **产物那一半一个字没松**：main.c 里既没有它的小节，也没有支点模块。
    """
    client, _ = devices_client
    client.post(
        "/api/my-devices",
        json={"device": {**DEVICE_BODY, "bus": "spi", "address": None,
                         "register": None, "expect": None}},
    )
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["mine_gyro"]},
    ).json()
    assert "hwcheck_custom_mine_gyro" not in body.get("main_c", ""), body
    assert "i2c_probe" not in body.get("main_c", ""), "不该顺手带上支点模块"
    plan = {item["slug"]: item for item in body["custom"]}
    assert set(plan) == {"mine_gyro"}, plan
    assert plan["mine_gyro"]["probes"] is False, plan
    assert plan["mine_gyro"]["plan"], "要说清为什么没有它的探测程序"
    assert plan["mine_gyro"]["wiring_text"] == "", "没有它的线，就不许编一行接线说明"


def test_the_page_console_table_carries_the_custom_retest_command(generate_client, tmp_path):
    """检测页命令区里的自建件那一行 = 产物里真认的那个字符（**页面与板上同源**）。

    工单 06 的票面："页面命令区显示自建件的字符与说明"。判据落在**同一次装配**
    上：预览载荷给的字符必须出现在生成的 main.c 的那条 `case` 里，而那个 case
    调的必须是**上电那一遍同一个函数**（输出同措辞的结构前提）。两处各建一张表
    就是这个功能最容易出的分家。
    """
    client, _ = generate_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    request = {
        "platform": PLATFORM_STM32,
        "debug_uart": True,
        "oled": False,
        "devices": ["mine_gyro"],
    }
    preview = client.post("/api/hwcheck/preview", json=request)
    assert preview.status_code == 200, preview.text
    commands = preview.json()["console"]["commands"]
    assert [item["slug"] for item in commands] == ["mine_gyro"], commands
    entry = commands[0]
    assert entry["command"] == "a", entry        # mine_gyro 的 g/y/r/o 全是保留字
    assert entry["tag"] == "自建件", entry        # 标注词来自服务端单源
    assert entry["name"] == DEVICE_BODY["name"], entry
    assert entry["description"], "说明恒非空（页面那一列不许是空的）"

    output_parent = tmp_path / "out-console"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate", json={**request, "parent_dir": str(output_parent)}
    )
    assert generated.status_code == 200, generated.text
    main_c = generated.json()["main_c"]
    assert f"case '{entry['command']}':" in main_c, (
        "页面说敲这个字符，产物里就必须真有这条 case：\n" + main_c[:500]
    )
    assert main_c.count("hwcheck_custom_mine_gyro();") == 2, (
        "上电那一遍 + 命令台复测那一遍（同一个函数 = 同一措辞）"
    )
    text = decode_c_string(main_c)
    assert f"[复测] mine_gyro" in text, text[:500]
    assert entry["description"] in text, "页面给的那句说明与板上回显同一句"


def test_an_unknown_slug_is_still_a_loud_failure(devices_client):
    """守卫不许松：**库内没有、也不是自建件**的 slug 照旧大声失败。

    这条是上面那条的对照组——"容忍自建件"必须与"容忍手滑写错"分开。
    """
    client, _ = devices_client
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["not_a_real_thing"]},
    )
    assert response.status_code == 400, response.text
    assert "not_a_real_thing" in response.json()["detail"]


def test_deleting_a_device_makes_its_id_an_unknown_slug_again(devices_client):
    """"自建件"这个身份是**当下的数据**，不是一份写死的名单。"""
    client, _ = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    assert client.delete("/api/my-devices/mine_gyro").status_code == 200
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["mine_gyro"]},
    )
    assert response.status_code == 400, response.text


# ---------------------------------------------------------------------------
# 落点纪律：不进产品库
# ---------------------------------------------------------------------------


def test_data_dir_is_not_the_module_library_or_masters_dir(devices_client):
    """写在配置目录下（与 updates/ / cache/ 同级），**不是**库根里的任何地方。"""
    client, data_dir = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    repo = Path(__file__).resolve().parents[1]
    assert (data_dir / MY_DEVICES_DIRNAME / "mine_gyro").is_dir()
    assert not (repo / "library" / MY_DEVICES_DIRNAME).exists()
    assert not (repo / MY_DEVICES_DIRNAME).exists()


def test_the_stored_json_holds_seven_bit_address_only(devices_client):
    """落盘只有 7 位那一个数：8 位读 / 写形式是派生的，不落盘（不许两个真相源）。"""
    client, data_dir = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    data = json.loads(
        (my_devices_dir(data_dir) / "mine_gyro" / DEVICE_JSON).read_text(encoding="utf-8")
    )
    assert data["address"] == 0x68
    assert "address_forms" not in data
    assert "read8" not in json.dumps(data)


# ---------------------------------------------------------------------------
# 资料 → 事实草稿（工单 hwcheck-unknown-device/07）：一次 LLM 抽取，草稿不落盘
# ---------------------------------------------------------------------------

DRAFT_MATERIAL = (
    "BMP280 气压传感器模块。供电 3.3V。I2C 地址：0x76（SDO 接地时）或 0x77。"
    "芯片 ID 寄存器 0xD0，读回值应为 0x58。"
)


def _good_device_draft():
    from contest_generator.my_device_draft import parse_device_draft

    raw = {
        "name": {"value": "BMP280", "source": "BMP280 气压传感器模块"},
        "bus": {"value": "i2c", "source": "I2C 地址：0x76"},
        "address": {"value": "0x76", "source": "I2C 地址：0x76"},
        "register": {"value": "0xD0", "source": "芯片 ID 寄存器 0xD0"},
        "expect": {"value": "0x58", "source": "读回值应为 0x58"},
        "notes": {"value": "SDO 接地时 0x76", "source": "SDO 接地时"},
    }
    return parse_device_draft(raw, DRAFT_MATERIAL)


def _draft_client(tmp_path, fake):
    """带可控 FakeLLM 的 TestClient（草稿端点的成功 / 降级两路共用）。"""
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app

    repo = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ctx = AppContext(
        config_path=data_dir / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: fake,
    )
    return TestClient(create_app(ctx)), data_dir


def test_draft_endpoint_extracts_a_draft_and_never_touches_disk(tmp_path):
    """成功路：200 + 草稿载荷；**数据目录一个字节不多**（未确认前不落盘——
    草稿只变成表单预填，确认后走既有的保存路径）。"""
    from tests.fakes import FakeLLM

    fake = FakeLLM(device_draft=_good_device_draft())
    client, data_dir = _draft_client(tmp_path, fake)
    response = client.post("/api/my-devices/draft", json={"text": DRAFT_MATERIAL})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is False
    assert body["message"] == ""
    assert body["draft"]["fields"]["address"] == {
        "value": "0x76", "source": "I2C 地址：0x76", "found": True,
    }
    assert body["draft"]["missing"] == []
    assert fake.draft_calls == [DRAFT_MATERIAL], "模型吃的必须是原文"
    assert not (data_dir / "hwcheck_devices").exists(), "草稿不许落盘"


def test_draft_endpoint_degrades_to_manual_fill_when_the_model_fails(tmp_path):
    """AI 不可用 = 200 + draft:null + degraded:true（页面走纯手填，不报错不阻断）。"""
    from contest_generator.llm import LLMError
    from tests.fakes import FakeLLM

    fake = FakeLLM(device_draft_error=LLMError("未配置 API Key"))
    client, _ = _draft_client(tmp_path, fake)
    response = client.post("/api/my-devices/draft", json={"text": DRAFT_MATERIAL})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["draft"] is None
    assert body["degraded"] is True
    assert "API Key" in body["message"]


def test_draft_endpoint_requires_material_text(tmp_path):
    from tests.fakes import FakeLLM

    client, _ = _draft_client(tmp_path, FakeLLM())
    for payload in ({}, {"text": ""}, {"text": "   "}):
        response = client.post("/api/my-devices/draft", json=payload)
        assert response.status_code == 400, f"{payload} → {response.text}"


def test_draft_endpoint_with_irrelevant_text_yields_all_missing(tmp_path):
    """票面点名的用例：喂一段**无关文本**，草稿必须是空字段 + "手册里没找到"。

    FakeLLM 缺省返回全字段未抽取的空草稿（= 模型如实说"资料里没有"的形态）；
    这条钉的是"没有值就绝不编一个默认值"。
    """
    from tests.fakes import FakeLLM

    client, _ = _draft_client(tmp_path, FakeLLM())
    response = client.post(
        "/api/my-devices/draft",
        json={"text": "今天天气不错，适合出门散步。"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is False
    assert body["draft"]["missing"] == [
        "name", "bus", "address", "register", "expect", "notes",
    ]
    assert body["draft"]["missing_text"] == "手册里没找到"
    for entry in body["draft"]["fields"].values():
        assert entry == {"value": "", "source": "", "found": False}


def test_draft_endpoint_unconfigured_is_a_hinted_400(tmp_path):
    """完全没配置（连 config 都没有）= 400 中文指路（去设置页填 API）——
    前端通用 catch 把它放进消息区，表单完好、不阻断（与降级路同一 UX）。
    """
    from fastapi.testclient import TestClient

    from contest_generator.webapp import AppContext, create_app

    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))
    response = client.post("/api/my-devices/draft", json={"text": "BMP280 地址 0x76"})
    assert response.status_code == 400, response.text
    assert "未配置 AI API" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 工程内快照与回读（工单 hwcheck-unknown-device/08）
# ---------------------------------------------------------------------------


def test_generate_archives_the_custom_device_into_the_project(generate_client, tmp_path):
    """生成后 `custom_device/<id>/` 里有定义快照 + 资料副本 + 抽取草稿；
    上下文清单不被归档污染（devices 照记、slugs 里没有它）。"""
    from contest_generator.context_manifest import read_context_fields

    client, data_dir = generate_client
    from tests.fakes import FakeLLM

    fake = FakeLLM()
    # 用带草稿的那支夹具：直接走保存端点 + 手工把资料/草稿带上（save 端点
    # 的载荷只收 device；资料与草稿在 08 起走 save 的可选字段，端点先不暴露——
    # 这里用域函数保存，端到端面在 generate / readback 两条路上）
    from contest_generator.my_devices import save_device, my_devices_dir, CustomDevice

    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x68, register=0x75, expect=0x68),
        material_text="I2C 地址：0x76（SDO 接地时）",
        draft={"missing": [], "missing_text": "手册里没找到"},
    )
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["mine_gyro"], "parent_dir": str(output_parent),
        },
    )
    assert response.status_code == 200, response.text
    project = Path(response.json()["output_dir"])
    snapshot = project / "custom_device" / "mine_gyro"
    assert (snapshot / "device.json").is_file(), "定义快照要进工程"
    assert (snapshot / "materials" / "material.txt").read_text(encoding="utf-8") == (
        "I2C 地址：0x76（SDO 接地时）"
    )
    assert (snapshot / "draft.json").is_file(), "抽取草稿要进工程"
    fields = read_context_fields(project)
    assert fields is not None and fields["devices"] == ["mine_gyro"]
    assert "custom_device" not in json.dumps(fields), "归档不许污染上下文清单"


def test_readback_prefers_the_project_snapshot_after_the_device_is_deleted(
    generate_client, tmp_path
):
    """用户删掉「我的器件」之后，已生成工程的回读**不变**（以工程内快照为准），
    并如实标注：这一行来自快照、条目已不存在（不静默、不报错）。"""
    from contest_generator.my_devices import save_device, my_devices_dir, CustomDevice

    client, data_dir = generate_client
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x68, register=0x75, expect=0x68),
    )
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["mine_gyro"], "parent_dir": str(output_parent),
        },
    )
    assert generated.status_code == 200, generated.text
    project = generated.json()["output_dir"]
    before = client.get("/api/hwcheck/project", params={"output_dir": project})
    assert before.status_code == 200, before.text
    import shutil

    shutil.rmtree(my_devices_dir(data_dir) / "mine_gyro")
    after = client.get("/api/hwcheck/project", params={"output_dir": project})
    assert after.status_code == 200, "删掉定义不许让工程读不回来"
    rows = after.json()["custom"]
    assert [row["slug"] for row in rows] == ["mine_gyro"], "计划仍完整"
    row = rows[0]
    assert row["snapshot"] is True, "回读以工程内快照为准"
    assert row["stored"] is False, "条目已不存在要如实标注"
    assert row["address_text"] == "0x68", "事实面与生成那次一致"


def test_readback_falls_back_to_the_data_dir_without_a_snapshot(generate_client, tmp_path):
    """08 之前的工程没有快照目录 → 回读走数据目录（既有行为，行上如实标
    snapshot=False / stored=True）。"""
    from contest_generator.my_devices import save_device, my_devices_dir, CustomDevice
    import shutil

    client, data_dir = generate_client
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x68, register=0x75, expect=0x68),
    )
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["mine_gyro"], "parent_dir": str(output_parent),
        },
    )
    assert generated.status_code == 200, generated.text
    project = Path(generated.json()["output_dir"])
    shutil.rmtree(project / "custom_device")  # 模拟 08 之前生成的工程
    readback = client.get("/api/hwcheck/project", params={"output_dir": str(project)})
    assert readback.status_code == 200, readback.text
    rows = readback.json()["custom"]
    assert [row["slug"] for row in rows] == ["mine_gyro"]
    assert rows[0]["snapshot"] is False
    assert rows[0]["stored"] is True


def test_save_endpoint_persists_material_and_draft_keys(devices_client):
    """保存端点收 `material_text` / `draft` 可选键 → 随定义落进条目（08 归档的
    源头走的是产品保存路径，不是只有域函数能落）；不带这两键的旧客户端零变化。"""
    client, data_dir = devices_client
    response = client.post("/api/my-devices", json={
        "device": DEVICE_BODY,
        "material_text": "I2C 地址：0x76（SDO 接地时）",
        "draft": {"missing": ["register"], "missing_text": "手册里没找到"},
    })
    assert response.status_code == 200, response.text
    entry = my_devices_dir(data_dir) / "mine_gyro"
    assert (entry / "materials" / "material.txt").read_text(encoding="utf-8") == (
        "I2C 地址：0x76（SDO 接地时）"
    )
    assert json.loads((entry / "draft.json").read_text(encoding="utf-8"))["missing"] == ["register"]
    # 旧的保存载荷（没有这两个键）照常工作，且不清掉已存的资料与草稿
    client.post("/api/my-devices", json={"device": {**DEVICE_BODY, "name": "改个名"}})
    assert (entry / "materials" / "material.txt").exists()
    assert (entry / "draft.json").exists()


def test_mixed_selection_archives_only_the_custom_device(generate_client, tmp_path):
    """混选（库内件 + 自建件——检测页上是同一个选择池，这是常态用法）：
    归档只含自建件；删掉数据条目后回读**仍完整**（快照分支在混选下照样生效——
    评审抓到的第一版按全量选中集判 `all()`，混选时永远走不进快照分支）。"""
    from contest_generator.my_devices import save_device, my_devices_dir, CustomDevice
    import shutil

    client, data_dir = generate_client
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x68, register=0x75, expect=0x68),
    )
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["led", "mine_gyro"], "parent_dir": str(output_parent),
        },
    )
    assert generated.status_code == 200, generated.text
    project = Path(generated.json()["output_dir"])
    assert (project / "custom_device" / "mine_gyro" / "device.json").is_file()
    assert not (project / "custom_device" / "led").exists(), "库内器件不进归档"

    shutil.rmtree(my_devices_dir(data_dir) / "mine_gyro")
    readback = client.get("/api/hwcheck/project", params={"output_dir": str(project)})
    assert readback.status_code == 200, readback.text
    rows = readback.json()["custom"]
    assert [row["slug"] for row in rows] == ["mine_gyro"], "混选删定义后计划仍完整"
    assert rows[0]["snapshot"] is True and rows[0]["stored"] is False


def test_readback_uses_the_snapshot_even_when_the_definition_was_later_edited(
    generate_client, tmp_path
):
    """票面第 2 条的「改了」半边：生成后改了「我的器件」的地址 → 回读仍是
    **生成那次**的事实（以快照为准，不是数据目录现读）。"""
    from contest_generator.my_devices import save_device, my_devices_dir, CustomDevice

    client, data_dir = generate_client
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x68, register=0x75, expect=0x68),
    )
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["mine_gyro"], "parent_dir": str(output_parent),
        },
    )
    assert generated.status_code == 200, generated.text
    project = generated.json()["output_dir"]
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x6B, register=0x75, expect=0x68),
    )
    readback = client.get("/api/hwcheck/project", params={"output_dir": project})
    assert readback.status_code == 200, readback.text
    row = readback.json()["custom"][0]
    assert row["address_text"] == "0x68", "回读以快照为准，不吃改后的定义"
    assert row["snapshot"] is True and row["stored"] is True


def test_partial_snapshot_falls_back_to_the_data_dir(generate_client, tmp_path):
    """部分快照（手删工程里一个条目的归档）→ 整体回退数据目录（all-or-nothing
    的既有口径），行上如实标 snapshot=False。"""
    from contest_generator.my_devices import save_device, my_devices_dir, CustomDevice
    import shutil

    client, data_dir = generate_client
    for device_id in ("mine_gyro", "mine_echo"):
        save_device(
            my_devices_dir(data_dir),
            CustomDevice(id=device_id, name="库外件 " + device_id, bus="i2c",
                         address=0x68, register=0x75, expect=0x68),
        )
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["mine_gyro", "mine_echo"], "parent_dir": str(output_parent),
        },
    )
    assert generated.status_code == 200, generated.text
    project = Path(generated.json()["output_dir"])
    shutil.rmtree(project / "custom_device" / "mine_echo")
    readback = client.get("/api/hwcheck/project", params={"output_dir": str(project)})
    assert readback.status_code == 200, readback.text
    rows = readback.json()["custom"]
    assert sorted(row["slug"] for row in rows) == ["mine_echo", "mine_gyro"]
    assert all(row["snapshot"] is False and row["stored"] is True for row in rows)


def test_readback_without_custom_devices_stays_clean(generate_client, tmp_path):
    """零自建件的工程：回读载荷**顶层不新增任何键**（snapshot / archive 这类
    字样一个都不出现）——「逐字与改动前一致」的结构面钉在这里。"""
    client, _ = generate_client
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": ["led"], "parent_dir": str(output_parent),
        },
    )
    assert generated.status_code == 200, generated.text
    project = generated.json()["output_dir"]
    assert not (Path(project) / "custom_device").exists(), "零自建件不建归档目录"
    readback = client.get("/api/hwcheck/project", params={"output_dir": project})
    assert readback.status_code == 200, readback.text
    payload = readback.json()
    assert payload["custom"] == []
    assert not [k for k in payload if "snapshot" in k or "archive" in k], sorted(payload)


# ---------------------------------------------------------------------------
# AI 排障带自建件事实（工单 hwcheck-unknown-device/09）
# ---------------------------------------------------------------------------


@pytest.fixture()
def triage_client(tmp_path):
    """真库 + 真母版 + **可观测的 FakeLLM**：排障端点送进模型的上下文从这里读。

    `generate_client` 的 `llm_factory` 每次现造一个 FakeLLM（拿不到实例），而本组
    用例的判据全落在"送进模型的上下文"上，所以单开一个带 holder 的夹具。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    repo = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    holder: dict[str, object] = {"llm": FakeLLM()}
    ctx = AppContext(
        config_path=data_dir / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=repo / "library" / "masters",
        ),
        llm_factory=lambda config: holder["llm"],
    )
    return TestClient(create_app(ctx)), data_dir, holder


def _generate_with_custom(client, tmp_path, devices) -> str:
    """生成一份含自建件的检测工程（09 的两条用例都从真工程出发）。"""
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
            "devices": list(devices), "parent_dir": str(output_parent),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["output_dir"]


def test_triage_context_carries_the_custom_device_facts(triage_client, tmp_path):
    """票面第 1 条：排障上下文里有「自建器件事实」（id / 名称 / 地址两种写法 /
    寄存器 / 期望值 / 探测形态 / 共总线），不是只在页面上有。"""
    client, _, holder = triage_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    output_dir = _generate_with_custom(client, tmp_path, ["led", "mine_gyro"])

    response = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "卖家给的六轴模块地址没有应答"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is False, body

    context = holder["llm"].triage_calls[-1]
    rows = context.customs_rows
    assert [row["slug"] for row in rows] == ["mine_gyro"], rows
    row = rows[0]
    assert row["name"] == "卖家给的六轴模块"
    # 地址两种写法都在（手册 0x68 与 8 位 0xD0 是同一个地址——填错地址最常见的坑）
    assert (row["address_text"], row["read8"], row["write8"]) == ("0x68", "0xD1", "0xD0")
    assert (row["register_text"], row["expect_text"]) == ("0x75", "0x68")
    assert row["probe_form"] == "板上判定"
    assert row["shared_with_library"] is False, "stm32 上 led 不占支点那对脚"
    # 材料里印出来（模型据此才知道这件该怎么查），且标明来源分量
    text = triage_context_text(context)
    assert "【自建器件】" in text and "0x68" in text, text
    assert "用户确认的事实" in text, text
    # 白名单：这件 id 进了单独那张表（库内词表里没有 mine_*）
    assert "mine_gyro" in context.facts.customs


def test_triage_context_prefers_the_project_snapshot(triage_client, tmp_path):
    """08 留的记账（09 结清）：排障的重投影**也吃工程内快照**。

    生成后改了「我的器件」的地址，排障上下文里仍是**那一次**的事实——与回读
    端点同一口径（不留"页面读快照、排障读现况"两条）。
    """
    client, data_dir, holder = triage_client
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x68, register=0x75, expect=0x68),
    )
    output_dir = _generate_with_custom(client, tmp_path, ["mine_gyro"])
    save_device(
        my_devices_dir(data_dir),
        CustomDevice(id="mine_gyro", name="卖家给的六轴模块", bus="i2c",
                     address=0x6B, register=0x75, expect=0x68),
    )

    client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "地址没有应答"},
    )
    row = holder["llm"].triage_calls[-1].customs_rows[0]
    assert row["address_text"] == "0x68", "排障上下文以工程内快照为准（不吃改后的定义）"


def test_triage_context_marks_a_shared_bus_in_the_real_chain(triage_client, tmp_path):
    """「与库内件共总线」的**是**那一格要走真链路（评审点：只用手搓 fixture 证不够）。

    stm32 上库内软 I2C 件（aht10 等六件）与支点 `i2c_probe` 共挂 PA6/PA7——选一件
    就是共总线，上下文要如实标"是"（共总线时"先查同一条总线上的库内件"才是有效
    线索；单挂时那句话反而是误导）。
    """
    client, _, holder = triage_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    output_dir = _generate_with_custom(client, tmp_path, ["aht10", "mine_gyro"])

    client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "地址没有应答"},
    )
    context = holder["llm"].triage_calls[-1]
    row = context.customs_rows[0]
    assert row["shared_with_library"] is True
    assert "与库内件共总线：是" in triage_context_text(context)


def test_triage_with_a_custom_device_still_degrades_without_blocking(
    triage_client, tmp_path
):
    """票面第 5 条：模型不可用 → 兜底建议照旧、检测记录照常落盘（**含自建件时
    也不阻断**——自建件是数据不是链路，模型挂了不影响把现象存下来）。"""
    from contest_generator.hwcheck_triage import HWCHECK_RECORD_FILENAME
    from contest_generator.llm import LLMError
    from tests.fakes import FakeLLM

    client, _, holder = triage_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    output_dir = _generate_with_custom(client, tmp_path, ["mine_gyro"])
    holder["llm"] = FakeLLM(triage_error=LLMError("连接被拒绝"))

    response = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "地址没有应答"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is True and "连接被拒绝" in body["message"]
    on_disk = json.loads(
        (Path(output_dir) / HWCHECK_RECORD_FILENAME).read_text(encoding="utf-8")
    )
    assert on_disk["symptom"] == "地址没有应答"
    assert on_disk["advice"]["degraded"] is True
