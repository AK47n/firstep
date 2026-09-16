"""跑法口径守卫（工单 test-speedup/01-02）：全套必须有上限，「卡住」当场变红。

**为什么值得一条用例守着**：这条口径解决的是「整支 pytest 间歇性卡住十分钟以上、
没有报错也没有栈、只能干等」（`docs/agents/local-environment.md` 2.5 节）——
它是靠 `pyproject.toml` 里两行配置生效的，而**配置被删掉时不会有任何症状**
（下次卡死时才会发现兜底没了）。所以这里钉三件事：

1. 全库默认超时在场，且值在合理区间（太小 = 把「机器忙」误判成卡死；
   太大 = 卡死时还是要等很久）；
2. `pytest-timeout` / `pytest-xdist` 在 `dev` 可选依赖里（配置声明了、依赖没声明 =
   换台机器就成了空配置）；
3. **仪器真的会响**——不是「配置读到了」，而是造一个会睡的用例、跑一次子进程 pytest、
   看它是否在阈值附近判红并打出 Timeout（照本仓库惯例：口径类守卫都要有反向验证）。

第 3 条是这条用例存在的核心理由：前两条只是读配置，读到了不代表插件在跑。
"""

from __future__ import annotations

import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 阈值允许区间：下限保证「不是随手填的 1 秒」，上限保证「卡死时不必等太久」。
MIN_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 600

# 行为验证用的阈值（子进程里临时覆盖）：小到几秒就能判红，又足够让 pytest 起完。
PROBE_TIMEOUT_SECONDS = 2


def _ini_options() -> dict:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["pytest"]["ini_options"]


def _dev_dependencies() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(data["project"]["optional-dependencies"]["dev"])


def test_whole_suite_has_a_bounded_timeout() -> None:
    """全库默认超时在场，且值在合理区间——删掉它 / 调到 1 秒都会红。"""
    options = _ini_options()
    assert "timeout" in options, (
        "pyproject.toml 缺 [tool.pytest.ini_options] timeout —— "
        "整支 pytest 卡死时又回到「无限等」（docs/agents/local-environment.md 2.5）"
    )
    value = options["timeout"]
    assert isinstance(value, int) and not isinstance(value, bool), f"timeout 必须是整数秒：{value!r}"
    assert MIN_TIMEOUT_SECONDS <= value <= MAX_TIMEOUT_SECONDS, (
        f"timeout={value} 越界（允许 {MIN_TIMEOUT_SECONDS}~{MAX_TIMEOUT_SECONDS}）："
        "太小会把机器忙误判成卡死，太大则卡死时仍要等很久"
    )


def test_timeout_plugin_is_a_declared_dev_dependency() -> None:
    """配置声明了插件、依赖也得声明——否则换台机器就是空配置（且不会有任何提示）。"""
    dev = _dev_dependencies()
    assert any(item.startswith("pytest-timeout") for item in dev), (
        f"dev 可选依赖里没有 pytest-timeout：{dev}"
    )
    assert any(item.startswith("pytest-xdist") for item in dev), (
        f"dev 可选依赖里没有 pytest-xdist（并行是 opt-in，但要能装上）：{dev}"
    )


def test_timeout_plugin_actually_fires(tmp_path: Path) -> None:
    """反向验证：**仪器真的会响**——会睡的用例必须被判红，而不是一直等下去。

    子进程外层再加一道 `subprocess.run(timeout=…)`：万一插件失效（用例会挂 120 秒），
    这条守卫自己也得有上限，不能把整场拖死——**守卫自己卡住是最讽刺的失败**。
    """
    probe = tmp_path / "test_deadline_probe.py"
    probe.write_text(
        "import time\n\n\ndef test_hangs_forever():\n    time.sleep(120)\n",
        encoding="utf-8",
    )
    started = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-o", f"timeout={PROBE_TIMEOUT_SECONDS}", "-o", "timeout_method=thread", str(probe)],
        cwd=str(tmp_path), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90,
    )
    elapsed = time.time() - started
    output = (proc.stdout or "") + (proc.stderr or "")

    assert proc.returncode != 0, f"会睡的用例居然没被判红（{elapsed:.1f}s）：{output[-600:]}"
    assert "Timeout" in output, f"没有打出超时标记——插件没在跑？{output[-600:]}"
    assert elapsed < 60, f"超时判红太慢（{elapsed:.1f}s），上限形同虚设"
