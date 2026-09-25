# -*- coding: utf-8 -*-
"""工单 02 的反证：把**当趟挑到的样本件**临时写进配方（模拟"下一批把它专精了"），
那几条走真实配方路径的用例必须**自动换一件样本、仍然绿**。

做法（真读真写，但**只回滚自己写的那一次**）：

1. **前置检查**：配方文件此刻的 sha256 记下来；
2. 挑一件样本（调测试里那个 helper，判据单源）；**就用它自己**（不写死 slug）当被专精件；
3. 给它补一条最小合法配方（stm32 一格），然后重挑一次——**必须换人**；
4. 起子进程跑 `tests/test_hwcheck.py` 里相关的那几条用例（preview / generate / project /
   挑件规则）；退出码为 0 才算"换了样本仍然全绿"；
5. **回滚**：只有在文件仍**逐字节等于我们写进去的那份**时才写回原字节——若窗口期内有人
   （另一个工单 / 编辑器）动过它，就**不碰**它并大声报错（宁可不还原，也不回滚别人的改动）。

判据三条一起成立才退 0：① 挑件真的换了人；② 那几条用例全绿；③ 回滚成功且逐字节保真。
任何一条不成立 = 非零退出（**反证没扎中会假绿**，这是本仓付过学费的一条）。

用法：`py -3 .scratch/hwcheck-specialize/probe-sample-decouple.py`
读数先落盘 `probe-sample-decouple.txt` 再打印。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECIPES = REPO / "library" / "hwcheck_recipes.json"
LINES: list[str] = ["=== 工单 02 反证：样本件被专精化之后，夹具自动换人 ===", ""]
FAILURES: list[str] = []


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pick() -> tuple[str, int, str]:
    """当前挑到的样本 + 候选总数 + 它的无参初始化名（判据单源：直接调测试里的 helper）。"""
    from tests.test_hwcheck import _unspecialized_candidates

    candidates = _unspecialized_candidates()
    if not candidates:
        return "（没有样本了）", 0, ""
    return candidates[0].slug, len(candidates), candidates[0].init.name


def _patch_for(init_name: str, headers: list[str], command: str) -> dict:
    """最小合法配方（真校验器会查引用与形状）——按该件自己头里的真名字写。

    只放 `include` + `init` + `console`：`usable` 由 init 撑住，`init_expect` 不写
    （返回类型不查，但写了会渲成比较式，没必要）。命令字符**现挑一个没被占用的**
    （`COMMAND_POOL` 里除去保留字与真库已声明的），免得日后那个字符被真配方占了、
    这条伪配方把用例搞红而人被误导成"夹具坏了"。
    """
    return {
        "include": {"headers": headers},
        "init": {"calls": [f"{init_name}()"]},
        "console": {"command": command, "description": "反证探针临时补的配方"},
    }


def _free_command(document: dict) -> str:
    """真库里还没被声明、也不是保留字的第一个命令字符（探针用）。"""
    from contest_generator.hwcheck_console import COMMAND_POOL

    used = {
        str(section.get("console", {}).get("command", "")).lower()
        for platforms in document.values() if isinstance(platforms, dict)
        for section in platforms.values() if isinstance(section, dict)
    }
    for char in COMMAND_POOL:
        if char not in used:
            return char
    raise SystemExit("命令池里没有空闲字符了——配方文件已经占满，反证探针跑不了")


original = RECIPES.read_bytes()
before_digest = _digest(original)
sample, count, init_name = _pick()
LINES.append(f"1) 前置：配方文件 sha256 = {before_digest[:16]}…；"
             f"候选样本 {count} 件，挑到的是 {sample!r}（无参初始化 {init_name}）")
LINES.append("")

document = json.loads(original.decode("utf-8"))
if sample in document:
    raise SystemExit(f"样本 {sample!r} 已经有配方了——这条反证的前提变了，先查挑件规则")

# 取该件 stm32 条目的头名（真头名，不猜）
from contest_generator.hwcheck_generic import read_module_headers  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402

LIB = REPO / "library" / "modules"
manifest = next(m for m in list_modules(LIB) if m.slug == sample)
headers = [Path(rel).name for rel, _text in read_module_headers(LIB, manifest, "stm32")]
if not headers:
    raise SystemExit(f"样本 {sample!r} 在 stm32 没有头文件——挑件规则应当已经排除它")

patched_bytes: bytes | None = None
restored = False
command = _free_command(document)
LINES.append(f"   （临时配方用的命令字符 = {command!r}：真库此刻没占、也不是保留字）")
try:
    document[sample] = {"stm32": _patch_for(init_name, headers, command)}
    patched_bytes = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    RECIPES.write_bytes(patched_bytes)
    after_sample, after_count, _after_init = _pick()
    switched = after_sample != sample
    if not switched:
        FAILURES.append("样本没有换人")
    LINES.append(f"2) 临时把 {sample!r} 写进配方（真头名 {headers}）之后："
                 f"候选 {after_count} 件，挑到 {after_sample!r}")
    LINES.append(f"   {'✓ 换人了' if switched else '✗ 没换（夹具还绑在旧样本上）'}")
    LINES.append("")
    LINES.append("3) 跑走真实配方路径的那几条用例（preview / generate / project / 挑件规则）：")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_hwcheck.py", "-q", "-k",
         "unspecialized or generic_sections or bus_scan"],
        cwd=str(REPO), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    for line in [ln for ln in (proc.stdout or "").splitlines() if ln.strip()][-3:]:
        LINES.append("   " + line.strip()[:160])
    if proc.returncode != 0:
        FAILURES.append(f"用例退出码 {proc.returncode}")
    LINES.append(f"   → 退出码 {proc.returncode}"
                 f"（0 = 换了样本仍然全绿；非 0 = 用例还绑死在旧样本上）")
finally:
    current = RECIPES.read_bytes()
    if patched_bytes is not None and current == patched_bytes:
        RECIPES.write_bytes(original)
        restored = _digest(RECIPES.read_bytes()) == before_digest
    else:
        FAILURES.append("配方文件在反证窗口期内被外力改动，未回滚（不覆盖别人的改动）")
    LINES.append("")
    LINES.append(f"4) 回滚：{'✓ 已按原字节写回，sha256 与改动前一致' if restored else '✗ 未回滚或回滚不保真'}"
                 f"（{_digest(RECIPES.read_bytes())[:16]}…）")

verdict = not FAILURES
LINES.append("")
LINES.append("结论：" + ("✓ 反证成立——样本被专精化后夹具自动换人且全绿，文件已还原"
                        if verdict else "✗ 反证不成立：" + "；".join(FAILURES)))

text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-sample-decouple.txt").write_text(
    text, encoding="utf-8")
print(text)
raise SystemExit(0 if verdict else 1)
