"""pytest 全局配置（平台组维护，脚本作者勿改）。

职责：
1. 设备 fixture：kuwo 等模块句柄注入（脚本不自己 u2.connect）；
2. 把 @pytest.mark.case 的用例编号写进 json 报告 metadata（平台覆盖率/结果解析的数据源）;
3. 失败现场自动采集：截图 + UI 层级（存 reports/failures/，接 Allure 时作为附件）；
4. 平台调度支持（执行引擎专用，本地手跑无需理会）：
   --jdo-cases    逗号分隔的用例编号：只执行这些标记的用例
   --jdo-progress 进度文件路径：每条用例结束追加一行 jsonl → 平台实时点亮执行矩阵；
                  配合 --collect-only 时改为写出可收集到的用例编号（预收集）
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# 保证 core/pages/config 可直接 import（无论从哪个目录发起 pytest）
sys.path.insert(0, str(Path(__file__).resolve().parent))

FAILURE_DIR = Path(__file__).resolve().parent.parent / "reports" / "failures"


# ---------------- 平台调度选项 ----------------
def pytest_addoption(parser):
    parser.addoption("--jdo-cases", default="",
                     help="逗号分隔的用例编号，仅执行带这些 @pytest.mark.case 标记的用例（平台执行引擎用）")
    parser.addoption("--jdo-progress", default="",
                     help="进度 jsonl 文件路径：每条用例结束追加一行（平台实时矩阵用）")


def _case_id(item) -> str:
    """取 @pytest.mark.case("XX-YYY-001") 标记的用例编号。"""
    mark = item.get_closest_marker("case")
    return mark.args[0] if mark and mark.args else ""


def pytest_collection_modifyitems(config, items):
    """--jdo-cases 过滤：只保留指定编号的用例（平台按任务范围选例）。"""
    wanted = {c.strip() for c in config.getoption("--jdo-cases").split(",") if c.strip()}
    if not wanted:
        return
    selected = [i for i in items if _case_id(i) in wanted]
    deselected = [i for i in items if _case_id(i) not in wanted]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


def pytest_collection_finish(session):
    """预收集模式（--collect-only + --jdo-progress）：写出实际可执行的用例编号。

    平台执行前先跑一次预收集 → 矩阵只画「框架里真实存在」的用例行，
    避免"映射了但脚本未提交仓库"的用例出现在真机执行矩阵里。
    """
    path = session.config.getoption("--jdo-progress")
    if path and session.config.option.collectonly:
        ids = [cid for item in session.items if (cid := _case_id(item))]
        Path(path).write_text(
            json.dumps({"collected": ids}, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------- 设备 fixtures ----------------
@pytest.fixture(scope="session")
def device():
    """会话级设备句柄；地址用环境变量 JDO_DEVICE 指定（默认 Audi 台架）。"""
    from core.device import get_device
    return get_device()


@pytest.fixture()
def kuwo(device):
    """酷我模块句柄：注入前确保模块已拉起（am start，品牌无关）。"""
    from core import adb_helper
    from config import settings
    adb_helper.am_start(device.serial, settings.ACTIVITIES["kuwo"])
    return device


# ---------------- 平台数据源钩子 ----------------
@pytest.hookimpl(optionalhook=True)
def pytest_json_runtest_metadata(item, call):
    """pytest-json-report 钩子：把 case_id 写进 json 报告 —— 平台按它统计覆盖率与结果。"""
    if call.when == "call":
        return {"case_id": _case_id(item)}


def _report_progress(item, report):
    """把单条用例结果追加到进度文件（jsonl），平台轮询它实时点亮矩阵。"""
    path = item.config.getoption("--jdo-progress")
    if not path:
        return
    outcome = "ok" if report.passed else ("skip" if report.skipped else "fail")
    line = json.dumps({
        "case_id": _case_id(item), "nodeid": item.nodeid,
        "outcome": outcome, "duration": round(report.duration, 2),
        "error": (str(report.longrepr).splitlines()[-1][:200] if report.failed else ""),
    }, ensure_ascii=False)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass   # 进度写失败不影响测试本身


# ---------------- 结果上报 + 失败现场 ----------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """call 结束上报进度；setup 阶段报错也上报（否则平台矩阵会缺格）；失败自动采集现场。"""
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and not report.passed):
        _report_progress(item, report)
    if report.when != "call" or not report.failed:
        return
    device = item.funcargs.get("device") or item.funcargs.get("kuwo")
    if device is None:
        return
    try:
        FAILURE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = FAILURE_DIR / f"{item.name}_{stamp}"
        device.screenshot(str(base) + ".png")
        (Path(str(base) + ".xml")).write_text(device.dump_hierarchy(), encoding="utf-8")
        _attach_to_allure(base)
    except Exception:
        pass   # 现场采集失败不影响测试结果本身


def _attach_to_allure(base: Path):
    """失败现场附进 Allure 报告（平台执行带 --alluredir 时生效，本地手跑静默跳过）。"""
    try:
        import allure
        allure.attach.file(str(base) + ".png", name="失败截图",
                           attachment_type=allure.attachment_type.PNG)
        allure.attach.file(str(base) + ".xml", name="UI 层级",
                           attachment_type=allure.attachment_type.XML)
    except Exception:
        pass
