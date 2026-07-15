"""外部框架执行适配器的共用内核 —— 解压包 / 进度插件 / 跑 pytest 并实时点亮矩阵。

Media_automation 与 Zcode 两套适配器都调这里，差异只在各自的：
- 用例编号 ↔ nodeid 映射来源（CSV / markdown）；
- 设备注入方式（环境变量 / 改写 config.yaml）。
执行、进度回填、超时兜底等通用逻辑收口在本模块，避免重复那段易错的 tail 循环。
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from .. import config

BUNDLE_ROOT = config.DATA_DIR / "frameworks"     # 解压后的可运行副本根目录

# 非侵入进度插件：pytest 每条用例结束写一行 jsonl 到 JDO_PROGRESS 指向的文件。
# 放进解压目录、用 -p 激活，不改包源码。
PROGRESS_PLUGIN = '''# 平台注入的进度插件（勿改）：把每条用例结果实时写到 JDO_PROGRESS 指向的 jsonl
import json, os
_P = os.environ.get("JDO_PROGRESS", "")


def pytest_runtest_logreport(report):
    if not _P:
        return
    # 通过/失败在 call 阶段；跳过在 setup 阶段
    if not (report.when == "call" or (report.when == "setup" and report.skipped)):
        return
    outcome = "ok" if report.passed else ("skip" if report.skipped else "fail")
    err = ""
    if report.failed:
        err = str(report.longrepr).splitlines()[-1][:200] if report.longrepr else ""
    try:
        with open(_P, "a", encoding="utf-8") as f:
            f.write(json.dumps({"nodeid": report.nodeid, "outcome": outcome, "error": err},
                               ensure_ascii=False) + "\\n")
    except OSError:
        pass
'''

PLUGIN_FILENAME = "jdo_progress.py"    # 解压目录内的插件文件名（-p jdo_progress 激活）


def session_timeout(n_tests: int) -> int:
    """单品牌 pytest 会话超时：按测试数给预算（media ADB-XML 慢，固定 600s 必截断全量），
    下限 REAL_RUN_TIMEOUT、上限 REAL_RUN_MAX。"""
    return min(max(config.REAL_RUN_TIMEOUT, n_tests * config.REAL_RUN_PER_TEST),
               config.REAL_RUN_MAX)


def prepare_bundle(script_id: int, file_path: str) -> Path:
    """把上传包解压到可运行目录（按 脚本id+文件指纹 缓存），放入进度插件，返回目录。

    缓存 key 含文件路径指纹：版本覆盖/激活切换后 file_path 变化 → 自动落到新目录，
    保证跑的永远是当前激活版本的包；同脚本的旧缓存目录顺手清掉，不堆磁盘垃圾。
    """
    tag = hashlib.md5(str(file_path).encode("utf-8")).hexdigest()[:8]
    dest = BUNDLE_ROOT / f"fw_{script_id}_{tag}"
    if BUNDLE_ROOT.exists():
        for p in BUNDLE_ROOT.glob(f"fw_{script_id}_*"):
            if p != dest:
                shutil.rmtree(p, ignore_errors=True)
        legacy = BUNDLE_ROOT / f"fw_{script_id}"          # 多版本之前的旧命名
        if legacy.exists():
            shutil.rmtree(legacy, ignore_errors=True)
    marker = dest / ".jdo_ready"
    if marker.exists():
        return dest
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(file_path) as zf:
        for info in zf.infolist():
            if any(x in info.filename for x in ("__pycache__", ".git/", ".pytest_cache")):
                continue
            zf.extract(info, dest)
    # 若包内是「单层顶层目录」结构，解压后 dest 下只有一个文件夹 → 上提为根
    entries = [p for p in dest.iterdir() if p.name != ".jdo_ready"]
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for p in inner.iterdir():
            shutil.move(str(p), str(dest / p.name))
        inner.rmdir()
    (dest / PLUGIN_FILENAME).write_text(PROGRESS_PLUGIN, encoding="utf-8")
    marker.write_text("ok", encoding="utf-8")
    return dest


def collect_nodeids(bundle_dir: Path, testpath: str = "") -> list:
    """pytest --collect-only 收集包内真实 nodeid（覆盖 pytest.ini 的 addopts 干扰）。"""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "--color=no",
           "-o", "addopts=", "-p", "no:cacheprovider"]
    if testpath:
        cmd.append(testpath)
    try:
        proc = subprocess.run(cmd, cwd=str(bundle_dir), capture_output=True,
                              timeout=config.COLLECT_TIMEOUT)
        out = proc.stdout.decode("utf-8", errors="replace")
        return [ln.strip() for ln in out.splitlines() if "::" in ln]
    except Exception:
        return []


def track_pytest(job: dict, rows: list, brand: str, bi: int, bundle_dir: Path,
                 node_rows: dict, cmd: list, env: dict, mark, add_log, fw_label: str):
    """跑一个 pytest 会话并实时点亮矩阵（Media/Zcode 共用）。

    node_rows: {nodeid: [矩阵行号...]} —— 一个测试可覆盖多条官方用例（多行）。
      ★ 必须按包内「自然收集顺序」插入（调用方保证），不能排序：很多框架按
      test_01→02→03 的文件序设计、用例间有状态依赖，乱序会破坏其假设。
    cmd/env:   调用方组装好的 pytest 命令与环境（含 --alluredir、-p jdo_progress、JDO_PROGRESS）。
    mark/add_log: run_service 提供的格子标记 / 日志回调。
    """
    nodeids = list(node_rows)          # 保持插入(=收集)顺序，勿排序
    progress_file = Path(env["JDO_PROGRESS"])
    log_file = config.PROGRESS_DIR / f"{job['id']}_{bi}_{fw_label}.log"
    config.PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

    if nodeids:
        mark(node_rows[nodeids[0]][0], bi, "run")   # 第一批行先亮「执行中」

    finished_nodes = set()
    truncated = False        # 终止/超时截断：剩余行记「未执行」(na) 而非失败
    proc = None
    try:
        with open(log_file, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, cwd=str(bundle_dir), stdout=lf,
                                    stderr=subprocess.STDOUT, env=env)
            deadline = time.time() + session_timeout(len(nodeids))
            pos = 0
            while True:
                if progress_file.exists():
                    with open(progress_file, "r", encoding="utf-8") as pf:
                        pf.seek(pos)
                        while True:
                            line = pf.readline()
                            if not line or not line.endswith("\n"):
                                break
                            pos = pf.tell()
                            try:
                                rec = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            nid = rec.get("nodeid")
                            if nid not in node_rows or nid in finished_nodes:
                                continue
                            finished_nodes.add(nid)
                            ok = rec.get("outcome") == "ok"
                            for ci in node_rows[nid]:       # 点亮该测试覆盖的所有行
                                mark(ci, bi, "ok" if ok else "fail", count_done=True)
                            if not ok:
                                add_log(f"✗ {rows[node_rows[nid][0]][0]} @ {brand} "
                                        f"{rec.get('outcome')}"
                                        + (f"（{rec.get('error')}）" if rec.get("error") else ""))
                            for nnid in nodeids:            # 下一个未完成测试的首行亮「执行中」
                                if nnid not in finished_nodes:
                                    mark(node_rows[nnid][0], bi, "run")
                                    break
                if proc.poll() is not None and len(finished_nodes) >= len(nodeids):
                    break
                if proc.poll() is not None:
                    time.sleep(0.5)
                    if not progress_file.exists() or progress_file.stat().st_size <= pos:
                        break
                if job.get("stop"):
                    proc.kill()
                    truncated = True
                    add_log(f"⚠ {brand}台架 已按请求终止 pytest 会话")
                    break
                if time.time() > deadline:
                    proc.kill()
                    truncated = True
                    add_log(f"⚠ {brand}台架 执行超时，已终止")
                    break
                time.sleep(0.2)
    except Exception as e:
        if proc and proc.poll() is None:
            proc.kill()
        add_log(f"⚠ {brand}台架 执行线程异常：{type(e).__name__}: {e}")
    finally:
        # 未产出结果的测试：终止/超时截断 → 记「未执行」；异常无结果 → 记失败
        for nid in nodeids:
            if nid not in finished_nodes:
                for ci in node_rows[nid]:
                    mark(ci, bi, "na" if truncated else "fail", count_done=True)
        add_log(f"✓ {brand}台架 {fw_label} 执行结束 · {len(finished_nodes)}/{len(nodeids)} 测试完成")
