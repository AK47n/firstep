"""模块库真机验证：真实 HTTP + 真实 DeepSeek 跑 AI 录入全流程。

用法：python module_import.py <slug> <platform> <project_dir> <file1,file2,...> [deps]
例：python module_import.py ml_oled stm32 C:/Users/luoji/Desktop/2026C ml_libs/ml_oled.c,ml_libs/ml_oled.h,ml_libs/ml_oled_font.h
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_source(path: Path) -> str:
    """真实工程文件混编码（utf-8/gbk）：统一转码为 utf-8 再入库。"""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")  # 中文注释工程常见 GBK（逐飞库等）


def main() -> None:
    slug, platform, project_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    names = sys.argv[4].split(",")
    deps = sys.argv[5].split(",") if len(sys.argv) > 5 else []
    files = {n: read_source(Path(project_dir) / n) for n in names}

    print(f"=== {slug} 文件 {len(files)} 个，总 {sum(len(v) for v in files.values())} 字节 ===")

    # 1) AI 出草稿
    resp = post("/api/modules", {"slug": slug, "platform": platform, "files": files, "description": ""})
    draft = resp.get("draft", "")
    print(f"[草稿] {draft}\n")

    # 2) 用草稿走校验 + 入库
    resp = post(
        "/api/modules",
        {"slug": slug, "platform": platform, "files": files, "description": draft,
         "dependencies": deps},
    )
    print(f"[入库] slug={resp.get('slug')} platforms={list(resp.get('platforms', {}))}")


if __name__ == "__main__":
    main()
