"""Media_automation 框架的执行适配器（ADB-XML 驱动 · docs CSV 映射）。

框架专属部分：CSV 映射解析 + 环境变量注入台架（MEDIA_DEVICE_SERIAL）。
解压 / 进度插件 / 跑 pytest 并点亮矩阵等通用逻辑复用 runner_common。
"""
import csv
import io
import os
import zipfile
from pathlib import Path

from .. import config
from . import runner_common

# 复用共用的解压（含缓存 + 进度插件放置）
prepare_bundle = runner_common.prepare_bundle


def _find_mapping_csv(bundle_dir: Path):
    for p in sorted(bundle_dir.rglob("*.csv")):
        if "mapping" in p.name.lower():
            return p
    return None


def case_to_nodeid(bundle_dir: Path, case_ids: list) -> dict:
    """建 {case_id(KW-000x): nodeid}。case_id 由 CSV 的 excel_id 换算（KW-{excel_id:04d}）。"""
    csv_path = _find_mapping_csv(bundle_dir)
    if not csv_path:
        return {}
    want = set(case_ids)
    mapping = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            node = (r.get("automation_case") or "").strip()
            if not node:
                continue
            try:
                cid = f"KW-{int(str(r['excel_id']).strip()):04d}"
            except (ValueError, KeyError):
                continue
            if cid in want:
                mapping[cid] = node
    return mapping


def collectable(bundle_dir: Path, case_ids: list) -> set:
    """预收集：返回这批 case_id 中 nodeid 在包内真实可被 pytest 收集的集合。"""
    c2n = case_to_nodeid(bundle_dir, case_ids)
    collected = set(runner_common.collect_nodeids(bundle_dir, "tests"))
    return {cid for cid, nid in c2n.items() if nid in collected}


def run_brand(job: dict, rows: list, brand: str, bi: int, serial: str,
              bundle_dir: Path, mark, add_log):
    """真机跑该品牌整列：组装 pytest 命令与环境，委托 runner_common 执行 + 点亮矩阵。"""
    import sys

    # {nodeid: [行号]}，按包内自然收集顺序（尊重框架文件序，别打乱状态）
    c2n = case_to_nodeid(bundle_dir, [cid for _, cid in rows])
    nid_to_rows = {}
    for ci, (_, cid) in enumerate(rows):
        nid = c2n.get(cid)
        if nid:
            nid_to_rows.setdefault(nid, []).append(ci)
    order = runner_common.collect_nodeids(bundle_dir, "tests")
    node_rows = {n: nid_to_rows[n] for n in order if n in nid_to_rows}
    for n, v in nid_to_rows.items():
        node_rows.setdefault(n, v)

    progress_file = config.PROGRESS_DIR / f"{job['id']}_{bi}_media.jsonl"
    allure_dir = config.PROGRESS_DIR / f"allure_{job['id']}_{bi}"
    config.PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    env = {**os.environ,
           "MEDIA_DEVICE_SERIAL": serial,          # 包 config.settings 读它选台架
           "MEDIA_PROFILE": "oneinfo_kuwo",        # One Info 聚合包里的酷我
           "JDO_PROGRESS": str(progress_file)}
    cmd = [sys.executable, "-m", "pytest", *node_rows, "-q", "--color=no",
           "-p", "no:cacheprovider", "-p", runner_common.PLUGIN_FILENAME[:-3],
           "--alluredir", str(allure_dir)]

    add_log(f"› {brand}台架 真机执行 Media_automation · {len(node_rows)} 个测试覆盖 {len(rows)} 条用例")
    runner_common.track_pytest(job, rows, brand, bi, bundle_dir, node_rows, cmd, env,
                               mark, add_log, "media")
