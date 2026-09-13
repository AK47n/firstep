"""工单 newuser-download/04 的 install.bat 文案补丁（一次跑完、可重复跑）。

为什么要脚本而不是直接编辑：`install.bat` 是 **GBK 无 BOM + CRLF**（`.gitattributes` 的
`*.bat text eol=crlf` + `tests/test_onboarding_docs.py` 双重钉住），用文本编辑器容易改成
UTF-8 或 LF——那会让 CMD 在中文 Windows 上把中文提示读成乱码。

口径（每条都断言命中次数，防「静默没改」与「改了多处」两种失手）：
1. 完成提示后面补一行：以后启动只双击桌面快捷方式，不用再跑本脚本（L2 演练卡点 K5）。
2. `need_python` / `old_python` 分支各补一句「装完重新运行本脚本即可」。
3. 不动流程、不动步骤编号、不动快捷方式负载。
"""

from __future__ import annotations

from pathlib import Path

BAT = Path(__file__).resolve().parents[2] / "install.bat"

PATCHES: tuple[tuple[str, str, int], ...] = (
    # ---- 1. 完成提示：把「以后怎么办」说全 ----
    (
        "echo  安装完成！双击桌面的 firstep 快捷方式启动\r\n"
        "echo  （也可以双击本目录的 start-app.vbs；浏览器会自动打开 http://127.0.0.1:8000）\r\n",
        "echo  安装完成！双击桌面的 firstep 快捷方式启动\r\n"
        "echo  （也可以双击本目录的 start-app.vbs；浏览器会自动打开 http://127.0.0.1:8000）\r\n"
        "echo.\r\n"
        "echo  以后每次启动：双击桌面的 firstep 即可，不用再运行本脚本。\r\n",
        1,
    ),
    # ---- 2. 没装 Python ----
    (
        'echo 安装时勾选 "Add python.exe to PATH"，装完重新运行本脚本。\r\n',
        'echo 安装时勾选 "Add python.exe to PATH"，装完重新运行本脚本即可。\r\n',
        1,
    ),
    # ---- 3. Python 版本太旧 ----
    (
        "echo 请到 https://www.python.org/downloads/ 下载新版安装，装完重新运行本脚本。\r\n",
        "echo 请到 https://www.python.org/downloads/ 下载新版安装，装完重新运行本脚本即可。\r\n",
        1,
    ),
)


def main() -> int:
    raw = BAT.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "install.bat 不应是 UTF-8 BOM"
    text = raw.decode("gbk")  # 解不开就是编码口径被破坏，直接红
    lf_only = text.count("\n") - text.count("\r\n")
    assert lf_only == 0, f"install.bat 出现 {lf_only} 处裸 LF（必须全 CRLF）"

    for old, new, expect in PATCHES:
        found = text.count(old)
        assert found == expect, f"补丁锚点命中 {found} 次（期望 {expect}）：{old[:40]!r}"
        text = text.replace(old, new)

    BAT.write_bytes(text.encode("gbk"))

    # 复验字节口径
    after = BAT.read_bytes()
    assert not after.startswith(b"\xef\xbb\xbf")
    again = after.decode("gbk")
    assert after.decode("gbk").count("\n") - again.count("\r\n") == 0
    print(f"  已打补丁：{len(PATCHES)} 处；字节 {len(raw)} → {len(after)}")
    print("  编码：GBK 无 BOM + 全 CRLF（复验通过）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
