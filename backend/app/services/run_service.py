"""执行引擎：一次执行 = 任务 × 勾选品牌，产出矩阵进度与报告。

双模式策略（按品牌逐一决定，可混跑）：
- 真机模式：品牌在 config.REAL_DEVICE_MAP 中且 adb 可达 →
  subprocess 调 pytest（--jdo-cases 按任务选例；conftest 把每条结果实时追加到
  --jdo-progress jsonl，本引擎边跑边读、逐格点亮矩阵）；执行前先 --collect-only
  预收集，矩阵只画框架里真实存在的用例行。
- 模拟模式：品牌无可达台架时回退演示执行
  （节奏与原型一致：每格约 0.23s，固定失败 = 爱奇艺视频播放 @ 保时捷）。

全部品牌都是模拟 → 保持与原型完全一致的「逐格顺序点亮」；
只要有一个真机品牌 → 改为「品牌并行」（每品牌一个线程，一列独立推进）。
job 存内存（平台重启丢弃进行中的 job），执行完成即落库为报告，历史可查。
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .. import config, db
from . import media_runner, task_service, zcode_runner

# 外部框架 -> 执行适配器（run_brand / prepare_bundle / collectable 同签名）
_ADAPTERS = {
    config.FRAMEWORK_MEDIA: media_runner,
    config.FRAMEWORK_ZCODE: zcode_runner,
}

_jobs: dict = {}                 # job_id -> 进度字典（前端轮询读取）
_lock = threading.Lock()

# 模拟模式每格耗时（秒），与原型 setTimeout 230ms 一致
_STEP_SECONDS = 0.23

# 任务无自动化用例时的兜底矩阵行（= 原型固定演示行，保证执行中心随时可演示）
_FALLBACK_ROWS = [
    ("酷我·播放", "KW-PLAY-001"), ("酷我·搜索", "KW-SRCH-002"),
    ("喜马·播放", "XM-PLAY-001"), ("爱奇艺·播放", "IQ-PLAY-001"),
    ("会议·入会", "MEET-JOIN-001"),
]


# ---------------------------------------------------------------- 计划与设备
def plan_rows(task_name: str) -> list:
    """预收集矩阵行：任务 App 范围内「已自动化」的用例，标签 = App短名·功能模块。"""
    task = task_service.get_task(task_name)
    rows = []
    if task:
        apps = json.loads(task["apps_json"])
        scope = task.get("scope") or "全部用例"
        with closing(db.get_conn()) as conn:
            for app in apps:
                q = ("SELECT DISTINCT c.id, c.module, c.priority FROM cases c"
                     " JOIN script_case sc ON sc.case_id = c.id"
                     " WHERE c.app = ? ORDER BY c.rowid")
                for r in conn.execute(q, (app,)):
                    if scope == "仅 P0" and r["priority"] != "P0":
                        continue
                    if scope == "仅 P1" and r["priority"] != "P1":
                        continue
                    short = config.APP_SHORT.get(app, app)
                    rows.append((f"{short}·{r['module']}", r["id"]))
    return rows or list(_FALLBACK_ROWS)


def _probe_device(serial: str) -> bool:
    """探测台架可达性：adb connect → adb root → get-state。

    必须 root：该车机固件用 SELinux 包策略（mangle 表 selinux_test_automation 链）
    拦截自动化端口 6790/7912/9008 的回环流量，非 root 域的 uiautomator2 服务
    起得来但连不上（表现为反复 server not ready）；root 后进入宽容域即放行。
    台架重启后 adbd 会掉回非 root，所以每次执行前都补一次（已 root 时无副作用）。
    """
    try:
        if ":" in serial:
            subprocess.run(["adb", "connect", serial], capture_output=True, timeout=8)
        subprocess.run(["adb", "-s", serial, "root"], capture_output=True, timeout=10)
        if ":" in serial:                      # root 会重启 adbd，网络设备需重连
            time.sleep(1)
            subprocess.run(["adb", "connect", serial], capture_output=True, timeout=8)
        # 清理残留的 u2 服务进程：异常退出的会话会留下死锁进程霸占 9008 端口，
        # 导致后续 u2 全部 server not ready（新会话由 uiautomator2 自行拉起）
        subprocess.run(["adb", "-s", serial, "shell", "pkill", "-9", "-f", "com.wetest.uia2.Main"],
                       capture_output=True, timeout=8)
        out = subprocess.run(["adb", "-s", serial, "get-state"],
                             capture_output=True, timeout=8)
        return out.stdout.decode().strip() == "device"
    except Exception:
        return False


def _collect_available(case_ids: list) -> set:
    """真机执行前预收集：返回框架仓库里真实可执行的用例编号集合。

    避免「已映射但脚本未提交仓库」的用例出现在真机矩阵里空跑。收集失败返回空集
    （调用方回退模拟模式），不阻塞执行。
    """
    config.PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = config.PROGRESS_DIR / f"collect_{uuid.uuid4().hex[:8]}.jsonl"
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "testcases", "-q", "--collect-only", "--color=no",
             "--jdo-cases", ",".join(case_ids), "--jdo-progress", str(out_file),
             "-p", "no:cacheprovider"],
            cwd=str(config.FRAMEWORK_DIR), capture_output=True,
            timeout=config.COLLECT_TIMEOUT)
        line = out_file.read_text(encoding="utf-8").strip()
        return set(json.loads(line).get("collected", []))
    except Exception:
        return set()
    finally:
        out_file.unlink(missing_ok=True)


def _resolve_execution(rows: list):
    """判断这批用例由哪个框架真机执行：返回 (framework, script_dict_or_None)。

    取覆盖这些用例最多的脚本的 framework —— 一个任务通常一个 App、对应一套框架。
    media_automation 走执行适配器（跑上传包），否则走我们的 framework。
    """
    case_ids = [cid for _, cid in rows]
    if not case_ids:
        return config.FRAMEWORK_JDO, None
    ph = ",".join("?" * len(case_ids))
    with closing(db.get_conn()) as conn:
        row = conn.execute(
            f"SELECT s.id, s.name, s.framework, s.file_path, COUNT(*) AS n"
            f" FROM script_case sc JOIN scripts s ON s.id = sc.script_id"
            f" WHERE sc.case_id IN ({ph}) GROUP BY s.id ORDER BY n DESC LIMIT 1", case_ids
        ).fetchone()
    if row and row["framework"] in _ADAPTERS:      # media_automation / media_zcode
        return row["framework"], dict(row)
    return config.FRAMEWORK_JDO, (dict(row) if row else None)


# ---------------------------------------------------------------- 启动与轮询
_FW_NAME = {config.FRAMEWORK_MEDIA: "Media_automation", config.FRAMEWORK_ZCODE: "Zcode(u2)",
            config.FRAMEWORK_JDO: "framework"}


def plan_rows_for_script(script_id: int):
    """脚本执行的矩阵行 + 框架/脚本信息：直接取该脚本覆盖的用例（不受任务范围/路由影响）。

    返回 (rows, framework, script_dict)；点哪个脚本就跑哪个框架的那批用例。
    """
    with closing(db.get_conn()) as conn:
        s = conn.execute("SELECT id, name, framework, file_path, app FROM scripts WHERE id = ?",
                         (script_id,)).fetchone()
        if not s:
            raise ValueError("脚本不存在")
        script = dict(s)
        rows = []
        for r in conn.execute(
                "SELECT sc.case_id, c.module FROM script_case sc"
                " LEFT JOIN cases c ON c.id = sc.case_id"
                " WHERE sc.script_id = ? ORDER BY sc.rowid", (script_id,)):
            short = config.APP_SHORT.get(script["app"], script["app"])
            rows.append((f"{short}·{r['module'] or r['case_id']}", r["case_id"]))
    framework = script["framework"] if script["framework"] in _ADAPTERS else config.FRAMEWORK_JDO
    return rows, framework, script


def _launch(rows: list, framework: str, script, brands: list, source: dict) -> str:
    """共用启动内核：预收集 → 建 job → 起后台执行线程，返回 job_id。

    source: {"task": 名} 或 {"script": 名} —— 仅用于 job 展示与报告落库标签。
    """
    bundle_dir = None
    modes = {}
    for b in brands:
        serial = config.REAL_DEVICE_MAP.get(b)
        modes[b] = serial if serial and _probe_device(serial) else None

    logs = []
    if any(modes.values()):
        adapter = _ADAPTERS.get(framework)
        if adapter and script:
            bundle_dir = adapter.prepare_bundle(script["id"], script["file_path"])
            available = adapter.collectable(bundle_dir, [cid for _, cid in rows])
        else:
            available = _collect_available([cid for _, cid in rows])
        real_rows = [r for r in rows if r[1] in available]
        if real_rows:
            rows = real_rows
            logs.append(f"› 预收集完成 · {_FW_NAME.get(framework, '框架')} 内可执行用例 {len(rows)} 条")
        else:
            logs.append("⚠ 框架内未收集到可执行用例，全部品牌转模拟执行")
            modes = {b: None for b in brands}

    for b in brands:
        logs.append(f"› 连接设备 {b}台架 ({modes[b]}) ✓ 真机" if modes[b]
                    else f"› 连接设备 {b}台架 (adb) ✓")

    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "task": source.get("task") or source.get("script", ""), "brands": brands,
        "rows": [r[0] for r in rows], "cells": {},
        "done": 0, "total": len(rows) * len(brands),
        "status": "running", "logs": logs, "summary": "",
        "framework": framework,
        "real": {b: bool(s) for b, s in modes.items()},
    }
    with _lock:
        _jobs[job_id] = job
    threading.Thread(target=_run_job, args=(job, rows, modes, framework, bundle_dir),
                     daemon=True).start()
    return job_id


def start(task_name: str, brands: list) -> str:
    """按任务执行：任务用例 → 覆盖最多的框架路由。"""
    rows = plan_rows(task_name)
    framework, script = _resolve_execution(rows)
    return _launch(rows, framework, script, brands, {"task": task_name})


def start_script(script_id: int, brands: list) -> str:
    """按脚本执行：直接跑该脚本对应框架的用例（脚本管理页的「执行」入口）。"""
    rows, framework, script = plan_rows_for_script(script_id)
    return _launch(rows, framework, script, brands, {"script": script["name"]})


def get_progress(job_id: str):
    """前端轮询接口的数据源；返回浅拷贝避免读到写一半的状态。"""
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


# ---------------------------------------------------------------- 执行调度
def _run_job(job: dict, rows: list, modes: dict, framework=None, bundle_dir=None):
    """总调度：全模拟走原型节奏的顺序执行；有真机则按品牌并行（按框架路由）。"""
    started = time.time()
    brands = job["brands"]

    if not any(modes.values()):
        _run_all_simulated(job, rows)                  # 与原型逐格顺序完全一致
    else:
        adapter = _ADAPTERS.get(framework)
        threads = []
        for bi, brand in enumerate(brands):
            if not modes[brand]:
                t = threading.Thread(target=_run_brand_simulated,
                                     args=(job, rows, brand, bi), daemon=True)
            elif adapter and bundle_dir:
                # 外部框架执行适配器（Media_automation / Zcode）：跑上传包自己的 pytest
                t = threading.Thread(
                    target=adapter.run_brand,
                    args=(job, rows, brand, bi, modes[brand], bundle_dir,
                          _mark_for(job), _log_for(job)), daemon=True)
            else:
                t = threading.Thread(target=_run_brand_real,
                                     args=(job, rows, brand, bi, modes[brand]), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=config.REAL_RUN_TIMEOUT + 30)

    elapsed = time.time() - started
    fail_by_brand = _count_fails(job, rows)
    fails = sum(fail_by_brand.values())
    with _lock:
        job["status"] = "done"
        job["summary"] = f"✓ 执行完成 · 通过 {job['total'] - fails}/{job['total']} · 失败 {fails}"
    _persist_reports(job, rows, fail_by_brand, elapsed)


def _sim_result(case_id: str, brand: str) -> bool:
    """模拟结果规则：固定「爱奇艺视频播放 @ 保时捷」失败（与原型演示一致）。"""
    return not (case_id == "IQ-PLAY-001" and brand == "保时捷")


def _mark(job: dict, ci: int, bi: int, state: str, count_done: bool = False):
    with _lock:
        job["cells"][f"{ci}-{bi}"] = state
        if count_done:
            job["done"] += 1


def _mark_for(job: dict):
    """给执行适配器（media_runner）用的格子标记回调，闭包绑定当前 job。"""
    def mark(ci, bi, state, count_done=False):
        _mark(job, ci, bi, state, count_done)
    return mark


def _log_for(job: dict):
    """给执行适配器用的日志追加回调（线程安全）。"""
    def add_log(text):
        with _lock:
            job["logs"].append(text)
    return add_log


def _run_all_simulated(job: dict, rows: list):
    """纯模拟：用例为外层、品牌为内层逐格推进（原型演示节奏）。"""
    for ci, (label, case_id) in enumerate(rows):
        for bi, brand in enumerate(job["brands"]):
            _mark(job, ci, bi, "run")
            time.sleep(_STEP_SECONDS)
            ok = _sim_result(case_id, brand)
            _mark(job, ci, bi, "ok" if ok else "fail", count_done=True)
            if not ok:
                with _lock:
                    job["logs"].append(f"✗ {label} @ {brand} 失败")


def _run_brand_simulated(job: dict, rows: list, brand: str, bi: int):
    """混跑时的模拟品牌线程：单列自上而下推进。"""
    for ci, (label, case_id) in enumerate(rows):
        _mark(job, ci, bi, "run")
        time.sleep(_STEP_SECONDS)
        ok = _sim_result(case_id, brand)
        _mark(job, ci, bi, "ok" if ok else "fail", count_done=True)
        if not ok:
            with _lock:
                job["logs"].append(f"✗ {label} @ {brand} 失败")


def _run_brand_real(job: dict, rows: list, brand: str, bi: int, serial: str):
    """真机品牌线程：一个 pytest 会话跑完该品牌整列。

    进度通道：conftest 把每条用例结果追加到 --jdo-progress jsonl，
    本线程边执行边 tail 该文件 → 实时点亮矩阵（无需等 pytest 退出）。
    """
    config.PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = config.PROGRESS_DIR / f"{job['id']}_{bi}.jsonl"
    log_file = config.PROGRESS_DIR / f"{job['id']}_{bi}.log"
    row_of = {}                                    # case_id -> 行号（同编号仅一行）
    for ci, (_, cid) in enumerate(rows):
        row_of.setdefault(cid, ci)

    cmd = [sys.executable, "-m", "pytest", "testcases", "-q", "--color=no",
           "--jdo-cases", ",".join(cid for _, cid in rows),
           "--jdo-progress", str(progress_file),
           # Allure 结果随执行产出（含失败截图附件），落库时移入报告专属目录
           "--alluredir", str(config.PROGRESS_DIR / f"allure_{job['id']}_{bi}"),
           "-p", "no:cacheprovider"]
    env = {**os.environ, "JDO_DEVICE": serial}

    _mark(job, 0, bi, "run")                       # 第一格先亮「执行中」
    finished_rows = set()
    proc = None
    try:
        with open(log_file, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, cwd=str(config.FRAMEWORK_DIR),
                                    stdout=lf, stderr=subprocess.STDOUT, env=env)
            deadline = time.time() + config.REAL_RUN_TIMEOUT
            pos = 0                                # 已消费的进度文件偏移
            while True:
                if progress_file.exists():
                    with open(progress_file, "r", encoding="utf-8") as pf:
                        pf.seek(pos)
                        while True:
                            line = pf.readline()   # 注意不能用 for line in pf：迭代中 tell() 被禁用
                            if not line:
                                break
                            if not line.endswith("\n"):
                                break              # 半行（conftest 正在写），下一轮重读
                            pos = pf.tell()
                            try:
                                rec = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            ci = row_of.get(rec.get("case_id"))
                            if ci is None or ci in finished_rows:
                                continue
                            finished_rows.add(ci)
                            ok = rec.get("outcome") == "ok"
                            _mark(job, ci, bi, "ok" if ok else "fail", count_done=True)
                            if not ok:
                                with _lock:
                                    job["logs"].append(
                                        f"✗ {rows[ci][0]} @ {brand} 失败"
                                        + (f"（{rec.get('error')}）" if rec.get("error") else ""))
                            # 下一待执行格亮「执行中」
                            for nci in range(len(rows)):
                                if nci not in finished_rows:
                                    _mark(job, nci, bi, "run")
                                    break
                if proc.poll() is not None and len(finished_rows) >= len(rows):
                    break
                if proc.poll() is not None:
                    time.sleep(0.5)                # 进程结束后再补读一轮尾部
                    if not progress_file.exists() or progress_file.stat().st_size <= pos:
                        break                      # 无新增内容（或从未产生）→ 收尾
                if time.time() > deadline:
                    proc.kill()
                    with _lock:
                        job["logs"].append(f"⚠ {brand}台架 执行超时，已终止 pytest 会话")
                    break
                time.sleep(0.2)
    except Exception as e:                         # 线程内任何异常都不能让矩阵悬空
        if proc and proc.poll() is None:
            proc.kill()
        with _lock:
            job["logs"].append(f"⚠ {brand}台架 执行线程异常：{type(e).__name__}: {e}")
    finally:
        # 没有结果的行（收集缺失/异常/超时）记失败，保证矩阵与统计完整
        for ci, (label, _) in enumerate(rows):
            if ci not in finished_rows:
                _mark(job, ci, bi, "fail", count_done=True)
                with _lock:
                    job["logs"].append(f"⚠ {label} @ {brand} 无执行结果，记失败（详见 {log_file.name}）")


# ---------------------------------------------------------------- 落库
def _count_fails(job: dict, rows: list) -> dict:
    """从矩阵格子统计各品牌失败数（真机/模拟统一口径；无结果=失败）。"""
    fails = {}
    for bi, brand in enumerate(job["brands"]):
        fails[brand] = sum(
            1 for ci in range(len(rows)) if job["cells"].get(f"{ci}-{bi}") != "ok")
    return fails


def _fmt_dur(seconds: float) -> str:
    """耗时展示：短的用秒（12.4s），长的用分钟（21m），与原型报告样式一致。"""
    return f"{seconds:.1f}s" if seconds < 60 else f"{round(seconds / 60)}m"


def _persist_reports(job: dict, rows: list, fail_by_brand: dict, elapsed: float):
    """执行结束落库：每个品牌一条报告 + 用例明细；并回写相关脚本的最近结果。"""
    task = task_service.get_task(job["task"])
    apps = json.loads(task["apps_json"]) if task else []
    app_label = apps[0] if len(apps) == 1 else "多 App"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(rows)
    failed_case_ids = set()
    new_report_ids = []                      # 落库后交给 Allure 后台预生成

    with closing(db.get_conn()) as conn:
        for bi, brand in enumerate(job["brands"]):
            fails = fail_by_brand[brand]
            cur = conn.execute(
                "INSERT INTO reports(task,app,brand,pass,total,dur,status,time,trigger_type)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (job["task"], app_label, brand, total - fails, total,
                 _fmt_dur(elapsed), "失败" if fails else "通过", now, "手动"))
            rid = cur.lastrowid
            new_report_ids.append(rid)
            # 真机品牌：把 pytest 产出的 Allure 结果移入报告专属目录（供惰性生成 HTML）
            allure_src = config.PROGRESS_DIR / f"allure_{job['id']}_{bi}"
            if allure_src.exists() and any(allure_src.iterdir()):
                dst = config.ALLURE_RESULTS_DIR / str(rid)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(allure_src), str(dst))
            for ci, (label, case_id) in enumerate(rows):
                res = "ok" if job["cells"].get(f"{ci}-{bi}") == "ok" else "fail"
                if res == "fail":
                    failed_case_ids.add(case_id)
                conn.execute("INSERT INTO report_cases(report_id,case_id,name,result) VALUES(?,?,?,?)",
                             (rid, case_id, label.split("·", 1)[-1], res))
        # 回写脚本「最近结果」：本次跑到的用例所属脚本，含失败用例标 fail，否则标 ok
        ran_ids = [case_id for _, case_id in rows]
        ph = ",".join("?" * len(ran_ids))
        for (sid,) in conn.execute(
                f"SELECT DISTINCT script_id FROM script_case WHERE case_id IN ({ph})", ran_ids):
            has_fail = False
            if failed_case_ids:
                fph = ",".join("?" * len(failed_case_ids))
                has_fail = conn.execute(
                    f"SELECT 1 FROM script_case WHERE script_id=? AND case_id IN ({fph}) LIMIT 1",
                    [sid, *failed_case_ids]).fetchone() is not None
            conn.execute("UPDATE scripts SET last_result=? WHERE id=?",
                         ("fail" if has_fail else "ok", sid))
        conn.commit()

    # 新报告立即后台预生成 Allure（高优先级）→ 用户点开报告中心时已就绪
    from . import allure_service
    for rid in new_report_ids:
        allure_service.enqueue(rid)
