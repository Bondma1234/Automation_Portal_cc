"""Allure 报告服务：结果收集 → HTML 生成（预生成 + 惰性兜底）→ 静态托管路径。

数据来源两条路（对调用方透明）：
1. 真机执行：run_service 给 pytest 加 --alluredir，落库时把结果目录移到
   reports/allure-results/<报告id>/（含 allure-pytest 的完整步骤与失败附件）；
2. 模拟执行 / 种子报告：生成时按 report_cases 明细合成最简 Allure 结果 JSON，
   保证平台里每一份报告都能打开 Allure（演示不落空）。

生成时机（allure generate 是 Java CLI，单次 5~15s，省不掉但可以挪到点击之前）：
- 执行落库后立即入队后台预生成（enqueue，高优先级）→ 用户点击时已就绪，秒开；
- 服务启动后预热历史缺失的报告（warm_up，低优先级）；
- 点击时兜底（ensure_html）：极端情况（刚启动就点/HTML 被清理）才会现场生成。
队列串行消费（同一时刻只跑一个 JVM），每报告一把锁防「点击」与「预生成」撞车。
"""
import json
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime
from itertools import count

from .. import config, db

# ---------------- 后台预生成队列 ----------------
_queue: "queue.PriorityQueue" = queue.PriorityQueue()   # (优先级, 序号, 报告id)
_seq = count()                                          # 同优先级按入队顺序
_worker_started = False
_worker_guard = threading.Lock()
_report_locks: dict = {}                                # report_id -> Lock
_locks_guard = threading.Lock()


def _lock_for(report_id: int) -> threading.Lock:
    with _locks_guard:
        return _report_locks.setdefault(report_id, threading.Lock())


def _ensure_worker():
    """惰性启动唯一的后台生成线程（守护线程，随服务退出）。"""
    global _worker_started
    with _worker_guard:
        if not _worker_started:
            threading.Thread(target=_worker, daemon=True, name="allure-worker").start()
            _worker_started = True


def _worker():
    while True:
        _, _, rid = _queue.get()
        try:
            ensure_html(rid)
        except Exception:
            pass    # 预生成失败不致命：用户点击时会再试，错误信息走接口给前端
        finally:
            _queue.task_done()


def purge(report_id: int):
    """删除该报告的全部 Allure 产物（结果目录 + HTML 目录，含截图/录屏附件）。

    与生成互斥：拿同一把报告锁再删，避免「删到一半、后台预生成又把目录写回来」。
    报告的 DB 记录应已先删——生成器兜底合成需要报告数据，查不到会干净地失败。
    """
    with _lock_for(report_id):
        shutil.rmtree(config.ALLURE_RESULTS_DIR / str(report_id), ignore_errors=True)
        shutil.rmtree(config.ALLURE_HTML_DIR / str(report_id), ignore_errors=True)


def enqueue(report_id: int, priority: int = 0):
    """报告入队预生成。priority 0=执行新产出（优先），1=启动预热积压。

    重复入队无害：生成前有「已存在即跳过」检查。
    """
    _ensure_worker()
    _queue.put((priority, next(_seq), report_id))


def warm_up():
    """启动预热：把所有缺 HTML 的报告排进低优先级队列（本函数即刻返回，不阻塞启动）。"""
    with closing(db.get_conn()) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM reports ORDER BY id DESC")]
    for rid in ids:
        if not (config.ALLURE_HTML_DIR / str(rid) / "index.html").exists():
            enqueue(rid, priority=1)

# 模拟失败用例的现场文案（与前端报告详情里的占位一致）
_SIM_FAIL_MESSAGE = ("校验 media_session 状态 … 期望 PLAYING，实际 PAUSED ✗\n"
                     "AssertionError: 播放未生效（疑似登录态失效）")


def _dur_seconds(dur: str) -> float:
    """'12.4s' / '21m' → 秒数；解析失败按 60s。"""
    m = re.match(r"([\d.]+)\s*([sm])", dur or "")
    if not m:
        return 60.0
    return float(m.group(1)) * (60 if m.group(2) == "m" else 1)


def _synthesize_results(report: dict, cases: list, out_dir):
    """按报告明细合成 Allure 结果 JSON（allure2 的 *-result.json 最简字段集）。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        start_ms = int(datetime.strptime(report["time"], "%Y-%m-%d %H:%M").timestamp() * 1000)
    except ValueError:
        start_ms = int(time.time() * 1000)
    per_case_ms = int(_dur_seconds(report["dur"]) * 1000 / max(len(cases), 1))

    for i, c in enumerate(cases):
        failed = c["result"] != "ok"
        rec = {
            "uuid": uuid.uuid4().hex,
            "historyId": c["case_id"],                      # 同用例跨报告可对比历史
            "name": f'{c["case_id"]} {c["name"]}',
            "fullName": c["case_id"],
            "status": "failed" if failed else "passed",
            "stage": "finished",
            "start": start_ms + i * per_case_ms,
            "stop": start_ms + (i + 1) * per_case_ms,
            "labels": [
                {"name": "suite", "value": report["task"]},
                {"name": "feature", "value": f'{report["brand"]}台架'},
                {"name": "framework", "value": "pytest"},
                {"name": "language", "value": "python"},
            ],
        }
        if failed:
            rec["statusDetails"] = {"message": _SIM_FAIL_MESSAGE}
        (out_dir / f"{rec['uuid']}-result.json").write_text(
            json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def ensure_html(report_id: int) -> str:
    """确保该报告的 Allure HTML 存在，返回访问路径；失败抛 ValueError（给前端 toast）。

    点击与后台预生成可能同时到达 → 每报告一把锁 + 锁内二次检查，只生成一次。
    """
    html_dir = config.ALLURE_HTML_DIR / str(report_id)
    url = f"/allure/{report_id}/index.html"
    if (html_dir / "index.html").exists():
        return url                                          # 已生成过（多为预生成命中）

    with _lock_for(report_id):
        if (html_dir / "index.html").exists():
            return url                                      # 等锁期间已被另一方生成

        # 1) 结果目录：真机执行已有；否则按 DB 明细合成
        results_dir = config.ALLURE_RESULTS_DIR / str(report_id)
        if not results_dir.exists() or not any(results_dir.glob("*-result.json")):
            with closing(db.get_conn()) as conn:
                row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
                if not row:
                    raise ValueError("报告不存在")
                cases = [dict(c) for c in conn.execute(
                    "SELECT case_id, name, result FROM report_cases WHERE report_id = ? ORDER BY rowid",
                    (report_id,))]
            if not cases:
                raise ValueError("该报告无用例明细，无法生成 Allure")
            _synthesize_results(dict(row), cases, results_dir)

        # 2) allure generate（.bat 需用 which 解析出完整路径）
        allure_bin = shutil.which("allure")
        if not allure_bin:
            raise ValueError("执行机未安装 allure 命令行（allure 不在 PATH）")
        proc = subprocess.run(
            [allure_bin, "generate", str(results_dir), "-o", str(html_dir), "--clean"],
            capture_output=True, timeout=config.ALLURE_GENERATE_TIMEOUT)
        if not (html_dir / "index.html").exists():
            detail = proc.stderr.decode("utf-8", errors="replace")[-200:]
            raise ValueError(f"Allure 生成失败：{detail or '未知错误'}")
        return url
