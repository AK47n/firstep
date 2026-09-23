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

from contest_generator.my_devices import (
    DEVICE_JSON,
    MY_DEVICES_DIRNAME,
    my_devices_dir,
)
from contest_generator.platforms import PLATFORM_STM32

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


@pytest.mark.parametrize("bad_id", ["gyro", "mine gyro", "mine_", "mine/../evil"])
def test_create_rejects_an_id_outside_the_mine_prefixed_grammar(devices_client, bad_id):
    client, _ = devices_client
    response = client.post(
        "/api/my-devices", json={"device": {**DEVICE_BODY, "id": bad_id}}
    )
    assert response.status_code == 400, response.text
    assert "mine_" in response.json()["detail"]


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
# 提前把自建件当器件发进检测计划：不许 400，也不许放松库外 slug 守卫
# ---------------------------------------------------------------------------


def test_passing_a_custom_device_id_as_a_device_does_not_400(devices_client):
    """本单的接缝：自建件还不是模块（工单 03 才接进渲染）。

    所以它**不进模块集**（那会被生成链上游的「库外 slug」守卫拒），但它出现在
    这次请求里不该让整次预览 400——页面已经能勾它了。
    """
    client, _ = devices_client
    client.post("/api/my-devices", json={"device": DEVICE_BODY})
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["mine_gyro"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["devices"] == ["mine_gyro"], "选择要回显（页面据此画 chip）"
    assert "mine_gyro" not in response.json()["main_c"], "这一版不生成它的探测代码"


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
