#!/usr/bin/env python
"""端到端演练：资料库增量更新全链路（工单 materials-update/07）。

在临时目录构造「假新版」资料库 + 本地 mock GitHub 源（releases 列表 JSON +
manifest + 批次 zip），从假旧资料库走：check（compare）→ apply（后台下载 +
卷级校验）→ 应用（解压 / 备份 / 删除 / 写基线）→ 断言文件落位、备份生成、
新清单写回、未变更批次原样、版本推进。

运行：python .scratch/materials-update/e2e/e2e_materials_update.py
输出：演练结论（断言失败 = 非 0 退出）。
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]  # .scratch/materials-update/e2e → 仓库根
sys.path.insert(0, str(REPO / "src"))

from contest_generator.materials_apply import apply_materials_update  # noqa: E402
from contest_generator.materials_task import ApplyTask  # noqa: E402
from contest_generator.materials_update import check_for_materials_update  # noqa: E402

STEPS: list[str] = []


def step(name: str) -> None:
    STEPS.append(name)
    print(f"[演练] {name}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# 1. 构造假旧资料库（v1.0.0 基线）
# ---------------------------------------------------------------------------


def build_old_materials(tmp: Path) -> tuple[Path, dict]:
    materials = tmp / "materials"
    (materials / "k230资料").mkdir(parents=True)
    (materials / "无线串口模块资料").mkdir(parents=True)
    (materials / "k230资料" / "keep.bin").write_bytes(b"keep-v1")
    (materials / "k230资料" / "change.bin").write_bytes(b"old-change")
    (materials / "k230资料" / "gone.bin").write_bytes(b"bye")
    (materials / "无线串口模块资料" / "stable.pdf").write_bytes(b"pdf-v1")
    old_manifest = {
        "version": "v1.0.0",
        "published_at": "2026-08-01T00:00:00Z",
        "batches": [
            {
                "slug": "k230",
                "name": "k230资料",
                "files": [
                    {"path": "k230资料/keep.bin", "size": 7, "sha256": sha256_of(materials / "k230资料/keep.bin")},
                    {"path": "k230资料/change.bin", "size": 10, "sha256": sha256_of(materials / "k230资料/change.bin")},
                    {"path": "k230资料/gone.bin", "size": 3, "sha256": sha256_of(materials / "k230资料/gone.bin")},
                ],
                "removed": [],
                "parts": [],
            },
            {
                "slug": "wireless-uart",
                "name": "无线串口模块资料",
                "files": [
                    {"path": "无线串口模块资料/stable.pdf", "size": 6, "sha256": sha256_of(materials / "无线串口模块资料/stable.pdf")},
                ],
                "removed": [],
                "parts": [],
            },
        ],
    }
    (materials / ".materials-manifest.json").write_text(
        json.dumps(old_manifest, ensure_ascii=False), encoding="utf-8"
    )
    return materials, old_manifest


# ---------------------------------------------------------------------------
# 2. mock GitHub 源（HTTP 服务）
# ---------------------------------------------------------------------------


def build_new_package(tmp: Path) -> tuple[dict, list[Path]]:
    """假新版：k230 批次 change.bin 修改 + new.bin 新增 + gone.bin 删除；
    wireless 批次不变。产出批次 zip + 新清单。"""
    zip_dir = tmp / "pack"
    zip_dir.mkdir()
    # 用真实差异文件构造增量 zip（条目路径 = 相对资料库根）
    zip_path = zip_dir / "firstep-materials-v1.1.0-k230.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("k230资料/change.bin", b"new-change")
        archive.writestr("k230资料/new.bin", b"new-file")
    new_manifest = {
        "version": "v1.1.0",
        "published_at": "2026-09-01T00:00:00Z",
        "batches": [
            {
                "slug": "k230",
                "name": "k230资料",
                "files": [
                    {"path": "k230资料/keep.bin", "size": 7, "sha256": "1" * 64},
                    {"path": "k230资料/change.bin", "size": 10, "sha256": "2" * 64},
                    {"path": "k230资料/new.bin", "size": 8, "sha256": "3" * 64},
                ],
                "removed": ["k230资料/gone.bin"],
                "parts": [
                    {
                        "zip_name": "firstep-materials-v1.1.0-k230.zip",
                        "size": zip_path.stat().st_size,
                        "sha256": sha256_of(zip_path),
                    }
                ],
            },
            {
                "slug": "wireless-uart",
                "name": "无线串口模块资料",
                "files": [
                    {"path": "无线串口模块资料/stable.pdf", "size": 6, "sha256": "4" * 64},
                ],
                "removed": [],
                "parts": [],
            },
        ],
    }
    return new_manifest, [zip_path]


class MockGitHubHandler(BaseHTTPRequestHandler):
    """极简 mock：/releases → JSON 列表；/files/<name> → 对应文件字节。"""

    manifest: dict = {}
    assets: dict[str, Path] = {}

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]  # 忽略 query 参数
        if path.startswith("/repos/AK47n/firstep/releases"):
            assets = [
                {
                    "name": "firstep-materials-v1.1.0.manifest.json",
                    "browser_download_url": self._base() + "/files/manifest.json",
                    "size": len(json.dumps(self.manifest, ensure_ascii=False)),
                },
            ]
            for name, path in self.assets.items():
                assets.append({
                    "name": name,
                    "browser_download_url": self._base() + "/files/" + name,
                    "size": path.stat().st_size,
                })
            body = json.dumps([{
                "tag_name": "materials-v1.1.0",
                "assets": assets,
            }], ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json", body)
            return
        if self.path.startswith("/files/"):
            name = self.path.split("/files/", 1)[1]
            if name == "manifest.json":
                self._send(200, "application/json",
                           json.dumps(self.manifest, ensure_ascii=False).encode("utf-8"))
                return
            path = self.assets.get(name)
            if path and path.is_file():
                self._send(200, "application/zip", path.read_bytes())
                return
        self._send(404, "text/plain", b"not found")

    def _base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # 静默
        pass


# ---------------------------------------------------------------------------
# 3. 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="mats-e2e-"))
    try:
        step(f"临时目录：{tmp}")
        materials, old_manifest = build_old_materials(tmp)

        new_manifest, zips = build_new_package(tmp)
        MockGitHubHandler.manifest = new_manifest
        MockGitHubHandler.assets = {
            z.name: z for z in zips
        }
        server = HTTPServer(("127.0.0.1", 0), MockGitHubHandler)
        port = server.server_port
        threading.Thread(target=server.serve_forever, daemon=True).start()

        # -- check（mock fetch，经 HTTP 走真 fetch 路径）
        step("check：mock GitHub 源")
        base = f"http://127.0.0.1:{port}"

        def fetch_json(url: str):
            import urllib.request
            # GitHub API 基址重写到 mock 服务器（路径与 query 保留）
            mock_url = url.replace("https://api.github.com", base)
            with urllib.request.urlopen(mock_url, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))

        def fetch_text(url: str):
            import urllib.request
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.read().decode("utf-8")

        from contest_generator.materials_update import check_for_materials_update
        # fetch_json 收到的是列表 URL——mock 服务按 path 判断，无需精确 URL
        result = check_for_materials_update(old_manifest, fetch_json, fetch_text)
        assert result["update_available"] is True, result
        assert result["latest_version"] == "v1.1.0"
        batch = result["batches"][0]
        assert batch["slug"] == "k230"
        assert batch["del_count"] == 1
        step(f"check 通过：新版 v1.1.0，k230 批次 {batch['add_count']} 增/"
             f"{batch['modify_count']} 改/{batch['del_count']} 删")

        # -- apply（下载：check 的 parts 的 zip_url 指向 mock）
        step("apply：后台下载 + 卷级校验")
        updates = tmp / "updates"
        task = ApplyTask(
            updates,
            result["batches"],
            download=None,  # 真 download_part（走 HTTP 到 mock）
        )
        task.run()
        assert task.state.value == "done", (task.state, task.error)
        step("下载完成（全部卷 SHA256 校验通过）")

        # -- apply 应用器
        step("应用：解压 / 备份 / 删除 / 写基线")
        apply_materials_update(
            materials_root=materials,
            manifest=new_manifest,
            zip_dir=updates / "materials",
            backup_dir=updates / "materials-backup",
            old_manifest=old_manifest,
        )
        # 断言
        assert (materials / "k230资料/change.bin").read_bytes() == b"new-change"
        assert (materials / "k230资料/new.bin").read_bytes() == b"new-file"
        assert not (materials / "k230资料/gone.bin").exists()
        assert (materials / "k230资料/keep.bin").read_bytes() == b"keep-v1"
        assert (materials / "无线串口模块资料/stable.pdf").read_bytes() == b"pdf-v1"
        backup = updates / "materials-backup"
        assert (backup / "k230资料/change.bin").read_bytes() == b"old-change"
        assert (backup / "k230资料/gone.bin").read_bytes() == b"bye"
        written = json.loads(
            (materials / ".materials-manifest.json").read_text(encoding="utf-8")
        )
        assert written["version"] == "v1.1.0"
        step("全部断言通过")

        server.shutdown()
        print(f"\n[OK] 演练完成：{len(STEPS)} 步全通过")
        return 0
    except Exception as exc:
        print(f"\n[失败] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
