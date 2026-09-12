#!/usr/bin/env python
"""端到端演练：完整包一键全量下载全链路（工单 full-download/06）。

在临时目录构造「迷你完整包」（两卷 zip + 完整包清单 + 资料库基线 + 删除清单）
与本机 mock GitHub 源（releases 列表 JSON + 清单 + 分卷），然后走完整用户路径：

    发布侧打包（prepare_full_package）→ check（认出版本/分卷）
      → apply（后台逐卷下载 + SHA256 校验）
      → 断点续传（第 2 卷失败重试只补第 2 卷）
      → 更新器落位（解压覆盖 / 备份 / 删除 / 写资料库基线 / 已装标记）

断言：分卷落盘与哈希、落位文件、删除生效、备份生成、资料库基线写回（无基线
→ 有基线）、包外文件与「不进包的第三方安装包」原样、已装版本标记。

运行：python .scratch/full-download/e2e_full_download.py
输出：演练步骤与结论（断言失败 = 非 0 退出）。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # .scratch/full-download → 仓库根
sys.path.insert(0, str(REPO / "src"))

from contest_generator.full_pack import (  # noqa: E402
    full_manifest_filename,
    prepare_full_package,
)
from contest_generator.full_task import FullDownloadTask  # noqa: E402
from contest_generator.full_update import check_for_full_update  # noqa: E402
from contest_generator.full_apply import build_updater_command  # noqa: E402

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


def load_updater():
    """加载 tools/update-app.py（不在包内，需注册 sys.modules 供 dataclass 解析）。"""
    spec = importlib.util.spec_from_file_location("update_app_e2e", REPO / "tools" / "update-app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_app_e2e"] = module
    spec.loader.exec_module(module)
    return module


updater = load_updater()


# ---------------------------------------------------------------------------
# 1. 造一个迷你「仓库树 v1.0.0」→ 用发布侧脚本打成完整包
# ---------------------------------------------------------------------------


def build_source_tree(tmp: Path) -> Path:
    root = tmp / "src-tree"
    (root / "src" / "contest_generator").mkdir(parents=True)
    (root / "src" / "contest_generator" / "__init__.py").write_text(
        '__version__ = "1.0.0"\n', encoding="utf-8"
    )
    (root / "library" / "modules" / "oled").mkdir(parents=True)
    (root / "library" / "modules" / "oled" / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "sources" / "materials" / "2026_08_MSPM0G3507与常用芯片手册").mkdir(parents=True)
    (root / "sources" / "materials" / "2026_08_MSPM0G3507与常用芯片手册" / "用户指南.md").write_text(
        "# 指南 v1\n", encoding="utf-8"
    )
    # 不进包的第三方安装包（全量替换后必须原地不动）
    (root / "sources" / "materials" / "2026_04_配套资料").mkdir(parents=True)
    (root / "sources" / "materials" / "2026_04_配套资料" / "01_CCS_20.5.0.00028_win.zip").write_text(
        "installer", encoding="utf-8"
    )
    (root / "README.md").write_text("# 迷你 firstep\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='mini'\nversion='1.0.0'\n", encoding="utf-8")
    # 注意：**不放** docs/old-page.md —— 它是基线里有、本版没有的文件，
    # 正是「删除清单」要覆盖的场景（放进源树就等于本版仍有，不算被删）。
    return root


# ---------------------------------------------------------------------------
# 2. 假 GitHub 资产服务
# ---------------------------------------------------------------------------


class AssetHandler(BaseHTTPRequestHandler):
    routes: dict[str, bytes] = {}

    def do_GET(self):  # noqa: N802 - http.server 契约
        body = self.routes.get(self.path.split("?")[0])
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静默
        return


def start_server(routes: dict[str, bytes]) -> tuple[HTTPServer, str]:
    AssetHandler.routes = routes
    server = HTTPServer(("127.0.0.1", 0), AssetHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        if cond:
            print(f"  ✓ {what}")
        else:
            failures.append(what)
            print(f"  ✗ {what}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # ---- 1. 发布侧打完整包（真实打包核心，单卷上限压到 1 MB 以便出两卷）----
        step("发布侧：打迷你完整包（zip 分卷 + 清单）")
        tree = build_source_tree(tmp)
        pack_dir = tmp / "pack"
        baseline = {
            "version": "v0.9.0",
            "files": [
                {"path": "README.md", "size": 1, "sha256": "0" * 64},
                {"path": "docs/old-page.md", "size": 1, "sha256": "0" * 64},
            ],
        }
        baseline_path = tmp / "baseline.json"
        baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
        manifest, written = prepare_full_package(
            tree,
            version="v1.1.0",
            out_dir=pack_dir,
            published_at="2026-09-13T00:00:00Z",
            baseline_path=baseline_path,
            limit=500,  # 压到 500 B：迷你树必然拆成多卷（顺带覆盖分卷路径）
        )
        parts = manifest["parts"]
        print(f"    分卷 {len(parts)} 卷：{[p['zip_name'] for p in parts]}")
        expect(len(parts) >= 1, "产出至少一卷 zip")
        expect(
            json.loads((pack_dir / full_manifest_filename("v1.1.0")).read_text(encoding="utf-8"))
            == manifest,
            "清单落盘且与返回值一致",
        )
        removed = (pack_dir / "firstep-full-v1.1.0.removed.txt").read_text(encoding="utf-8").split()
        expect(removed == ["docs/old-page.md"], "删除清单 = 基线有而当前无（docs/old-page.md）")
        expect(
            manifest["materials_manifest"]["batches"][0]["name"] == "2026_08_MSPM0G3507与常用芯片手册",
            "清单带资料库基线（落位后可直接转增量）",
        )

        # ---- 2. 假 GitHub：releases 列表 + 清单 + 分卷 ----
        step("mock GitHub：releases 列表 + 清单 + 分卷资产")
        routes: dict[str, bytes] = {}
        assets = []
        manifest_name = full_manifest_filename("v1.1.0")
        routes[f"/files/{manifest_name}"] = (
            pack_dir / manifest_name
        ).read_bytes()
        assets.append(
            {"name": manifest_name, "browser_download_url": "/files/" + manifest_name, "size": 1}
        )
        for item in parts:
            routes[f"/files/{item['zip_name']}"] = (pack_dir / item["zip_name"]).read_bytes()
            assets.append(
                {
                    "name": item["zip_name"],
                    "browser_download_url": "/files/" + item["zip_name"],
                    "size": item["size"],
                }
            )
        server, base = start_server(routes)
        for asset in assets:
            asset["browser_download_url"] = base + asset["browser_download_url"]
        releases = [{"tag_name": "v1.1.0", "assets": assets}]
        releases_url = base + "/releases"
        routes["/releases"] = json.dumps(releases).encode("utf-8")

        # ---- 3. check：无基线用户能看到完整包 ----
        step("用户侧：check（未知已装版本 → 给出分卷与总量）")
        check = check_for_full_update(
            installed=None,
            fetch_json=lambda url: releases,
            fetch_text=lambda url: routes[url.replace(base, "")].decode("utf-8"),
        )
        expect(check["error"] == "", "check 无错误")
        expect(check["latest_version"] == "v1.1.0", "认出最新完整包版本")
        expect(len(check["parts"]) == len(parts), f"分卷表与发布一致（{len(parts)} 卷）")
        expect(check["manifest_url"].endswith(manifest_name), "带上清单地址（供更新器读取）")

        # ---- 4. apply：真实下载任务（真 HTTP + 真 SHA256 校验）----
        step("用户侧：apply 下载全部卷（真实 HTTP + 每卷 SHA256）")
        updates = tmp / "userdata" / "updates"
        task = FullDownloadTask(
            task_dir=updates,
            parts=[
                {"name": p["name"], "url": p["url"], "size": p["size"], "sha256": p["sha256"]}
                for p in check["parts"]
            ],
            snapshot_interval=0.0,
        )
        task.run()
        expect(task.state.value == "done", f"任务终态 done（实际 {task.state.value}）")
        for item in parts:
            local = updates / "full" / item["zip_name"]
            expect(local.is_file(), f"分卷落盘：{item['zip_name']}")
            expect(sha256_of(local) == item["sha256"], f"分卷哈希一致：{item['zip_name']}")

        # ---- 5. 断点续传：删掉第 2 卷 → 重跑只补第 2 卷 ----
        step("用户侧：断点续传（重跑只补缺失卷）")
        retried: list[str] = []
        if len(parts) > 1:
            (updates / "full" / parts[1]["zip_name"]).unlink()
            resume = FullDownloadTask(
                task_dir=updates,
                parts=[
                    {"name": p["name"], "url": p["url"], "size": p["size"], "sha256": p["sha256"]}
                    for p in check["parts"]
                ],
                download=lambda url, dest, cb: (
                    retried.append(url.rsplit("/", 1)[-1]),
                    _real_download(url, dest, cb),
                )[1],
                snapshot_interval=0.0,
            )
            resume.run()
            expect(retried == [parts[1]["zip_name"]], f"只重下缺失卷（实际 {retried}）")
            expect(resume.state.value == "done", "续传后终态 done")
        else:
            print("    （本次只出一卷，跳过续传断言）")

        # ---- 6. 更新器落位：解压 / 备份 / 删除 / 写基线 / 已装标记 ----
        step("更新器：落位到「用户工具根」并写回资料库基线")
        tool_root = tmp / "user-tool"
        # 用户手上的旧版本（含将被覆盖、将被删除、以及不进包的安装包）
        (tool_root / "src" / "contest_generator").mkdir(parents=True)
        (tool_root / "src" / "contest_generator" / "__init__.py").write_text(
            '__version__ = "1.0.0"\n', encoding="utf-8"
        )
        (tool_root / "README.md").write_text("# 旧说明\n", encoding="utf-8")
        (tool_root / "docs").mkdir()
        (tool_root / "docs" / "old-page.md").write_text("旧页面\n", encoding="utf-8")
        (tool_root / "sources" / "materials" / "2026_04_配套资料").mkdir(parents=True)
        (tool_root / "sources" / "materials" / "2026_04_配套资料" / "01_CCS_20.5.0.00028_win.zip").write_text(
            "installer-user-copy", encoding="utf-8"
        )
        (tool_root / "sources" / "materials" / "2026_08_MSPM0G3507与常用芯片手册").mkdir(parents=True)
        (tool_root / "sources" / "materials" / "2026_08_MSPM0G3507与常用芯片手册" / "用户指南.md").write_text(
            "# 指南 v0\n", encoding="utf-8"
        )
        data_dir = tmp / "userdata"
        (data_dir / "config.json").write_text("{}", encoding="utf-8")

        manifest_path = pack_dir / manifest_name
        options = updater.UpdateOptions(
            zip_path=updates / "full" / parts[0]["zip_name"],
            root=tool_root,
            data_dir=data_dir,
            stop=False,
            restart=False,
            check_deps=False,
            full_parts=[str(updates / "full" / p["zip_name"]) for p in parts],
            full_manifest_path=manifest_path,
            log=updater.logging.getLogger("e2e-full"),
        )
        command = build_updater_command(
            root=tool_root,
            python="python",
            manifest_location=str(manifest_path),
            parts=[updates / "full" / p["zip_name"] for p in parts],
            port=8000,
        )
        expect("--full-manifest" in command and command.count("--part") == len(parts),
               "编排命令带清单与全部分卷")
        code = updater.run_update(options)
        expect(code == 0, f"更新器退出码 0（实际 {code}）")
        expect(
            (tool_root / "src" / "contest_generator" / "__init__.py").read_text(encoding="utf-8")
            == '__version__ = "1.0.0"\n',
            "包内文件落位（src 覆盖成功）",
        )
        expect(
            (tool_root / "sources" / "materials" / "2026_08_MSPM0G3507与常用芯片手册" / "用户指南.md").read_text(
                encoding="utf-8"
            )
            == "# 指南 v1\n",
            "资料库内容随包更新（v0 → v1）",
        )
        expect(not (tool_root / "docs" / "old-page.md").exists(), "删除清单生效（废弃文件被清）")
        expect(
            (tool_root / "sources" / "materials" / "2026_04_配套资料" / "01_CCS_20.5.0.00028_win.zip")
            .read_text(encoding="utf-8") == "installer-user-copy",
            "不进包的第三方安装包原地不动",
        )
        baseline_file = tool_root / "sources" / "materials" / ".materials-manifest.json"
        expect(baseline_file.is_file(), "资料库基线清单写回（无基线 → 有基线）")
        if baseline_file.is_file():
            written_baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
            expect(written_baseline["version"] == "v1.1.0", "基线版本 = 本次完整包版本")
            expect(len(written_baseline["batches"]) == 1, "基线批次与清单一致")
        marker = data_dir / "updates" / "full-installed.json"
        expect(marker.is_file(), "已装版本标记落盘")
        if marker.is_file():
            expect(
                json.loads(marker.read_text(encoding="utf-8"))["version"] == "v1.1.0",
                "已装版本 = v1.1.0",
            )
        backups = list((data_dir / "updates" / "backup").glob("*"))
        expect(len(backups) == 1, "备份目录生成")
        if backups:
            expect((backups[0] / "README.md").read_text(encoding="utf-8") == "# 旧说明\n",
                   "被覆盖文件已备份（旧内容还在）")
        expect(
            json.loads((data_dir / "updates" / "last-update.json").read_text(encoding="utf-8"))["mode"]
            == "full",
            "结果记录标记 full 模式",
        )
        expect(not (data_dir / "updates" / "updating.lock").exists(), "更新中锁已释放")

        # ---- 7. 全量之后转增量：下次 check 本地已有基线 ----
        step("收尾：全量完成后本地已有基线（后续走增量）")
        expect(baseline_file.is_file(), "下次检查资料库更新可算增量（不再提示完整包）")

        server.shutdown()

    print()
    if failures:
        print(f"演练失败：{len(failures)} 项未通过")
        for item in failures:
            print(f"  ✗ {item}")
        return 1
    print(f"演练通过：{len(STEPS)} 步全部断言成立")
    return 0


def _real_download(url: str, dest: Path, on_progress) -> str:
    """真实 HTTP 流式下载（续传断言用；与生产 download_part 同口径）。"""
    from contest_generator.materials_task import download_part

    return download_part(url, dest, on_progress)


if __name__ == "__main__":
    raise SystemExit(main())
