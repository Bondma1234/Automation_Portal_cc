"""Media_automation_Zcode 框架的执行适配器（uiautomator2 驱动 · markdown 映射）。

与 Media_automation 的两点差异，其余复用 runner_common：
1. 映射在 docs/用例覆盖矩阵.md（markdown 表格），且表里写的函数名 ≠ 真实 nodeid
   （真实 nodeid 带类名前缀、参数化 id 也不同）→ 靠「收集真实 nodeid + 按
   文件/函数名/中文参数子串匹配」建映射；
2. 设备不走环境变量，而是读 config/config.yaml 的 device.serial → 跑前改写该文件注入台架。
"""
import os
import re
from pathlib import Path

from .. import config
from . import runner_common

prepare_bundle = runner_common.prepare_bundle


def _find_matrix_md(bundle_dir: Path):
    for p in sorted(bundle_dir.rglob("*.md")):
        if "覆盖矩阵" in p.name or "coverage" in p.name.lower():
            txt = p.read_text(encoding="utf-8", errors="replace")
            if "Excel 编号" in txt or "自动化用例" in txt:
                return p
    return None


def parse_matrix(md_text: str) -> list:
    """解析覆盖矩阵 markdown → [(file, func_base, param_label, excel_id), ...]。

    - 段落标题 `### xxx(test_01_home.py)` 给出该表对应的测试文件；
    - 行 `| test_switch_tab[我的] | #10 | ... |` → 函数名 + 中文参数标签 + Excel 编号；
    - 编号取 `#数字`（`#390 衍生` 取 390）；`—`（无编号）跳过（无对应官方用例）。
    """
    entries, cur_file = [], None
    for line in md_text.splitlines():
        m = re.search(r"\((test_\w+\.py)\)", line)
        if m:
            cur_file = m.group(1)
            continue
        if not (cur_file and line.lstrip().startswith("|") and "test_" in line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        auto, code = cells[0], cells[1]
        num = re.search(r"#(\d+)", code)
        if not num:                               # — 无编号：跳过
            continue
        pm = re.match(r"(test_\w+?)(?:\[(.+)\])?$", auto)
        if not pm:
            continue
        entries.append((cur_file, pm.group(1), pm.group(2) or "", int(num.group(1))))
    return entries


def _unescape_u(s: str) -> str:
    """把 pytest 参数 id 里的字面 \\uXXXX 转回中文（pytest 默认转义非 ASCII 参数 id）。"""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def _parse_nodeid(nid: str):
    """真实 nodeid → (file_basename, func_base, param)。
    例 testcase/kuwo/test_01_home.py::TestKuwoHome::test_switch_tab[go_tab_my-\\u6211\\u7684]
       → ('test_01_home.py', 'test_switch_tab', 'go_tab_my-我的')
    参数解码回中文用于匹配覆盖矩阵；执行选例仍用原始 nodeid（转义形式才是真实 id）。
    """
    path, _, tail = nid.partition("::")
    file_base = path.rsplit("/", 1)[-1]
    func_full = tail.rsplit("::", 1)[-1]          # 去掉类名前缀
    fm = re.match(r"(test_\w+?)(?:\[(.+)\])?$", func_full)
    if not fm:
        return file_base, func_full, ""
    return file_base, fm.group(1), _unescape_u(fm.group(2) or "")


def case_to_nodeid(bundle_dir: Path, case_ids: list) -> dict:
    """建 {case_id(KW-000x): 真实 nodeid}。

    matrix 的函数名和真实 nodeid 对不上（类名前缀 + 参数 id 不同），故：
    收集真实 nodeid → 按 (文件, 函数名, 中文参数是子串) 匹配 matrix 条目 → 取 excel_id。
    """
    md = _find_matrix_md(bundle_dir)
    if not md:
        return {}
    entries = parse_matrix(md.read_text(encoding="utf-8", errors="replace"))
    want = set(case_ids)
    mapping = {}
    for nid in runner_common.collect_nodeids(bundle_dir, "testcase"):
        nf, nfunc, nparam = _parse_nodeid(nid)
        for efile, efunc, eparam, excel_id in entries:
            # 文件名 + 函数名一致；参数化条目要求 matrix 的中文标签是真实参数的子串
            if efile == nf and efunc == nfunc and (not eparam or eparam in nparam):
                cid = f"KW-{excel_id:04d}"
                if cid in want and cid not in mapping:
                    mapping[cid] = nid
                break
    return mapping


def collectable(bundle_dir: Path, case_ids: list) -> set:
    return set(case_to_nodeid(bundle_dir, case_ids).keys())


def _build_node_rows(bundle_dir: Path, rows: list) -> dict:
    """{nodeid: [矩阵行号...]}，按包内自然收集顺序排列（尊重框架 test_01→02→03 设计序）。"""
    c2n = case_to_nodeid(bundle_dir, [cid for _, cid in rows])
    nid_to_rows = {}
    for ci, (_, cid) in enumerate(rows):
        nid = c2n.get(cid)
        if nid:
            nid_to_rows.setdefault(nid, []).append(ci)
    order = runner_common.collect_nodeids(bundle_dir, "testcase")   # pytest 自然收集顺序
    node_rows = {n: nid_to_rows[n] for n in order if n in nid_to_rows}
    # 兜底：万一收集顺序里漏了（理论不会），补上剩余的
    for n, v in nid_to_rows.items():
        node_rows.setdefault(n, v)
    return node_rows


def _inject_device(bundle_dir: Path, serial: str):
    """把台架序列号写进 config/config.yaml（Zcode 只从该文件读设备，不认环境变量）。

    只替换 device.serial / u2_ip 两行，不动其它配置；正则行内替换，避免引入 yaml 依赖顺序问题。
    """
    cfg = bundle_dir / "config" / "config.yaml"
    if not cfg.exists():
        return
    ip = serial.split(":")[0]
    text = cfg.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r'(\n\s*serial:\s*)"[^"]*"', rf'\g<1>"{serial}"', text, count=1)
    text = re.sub(r'(\n\s*u2_ip:\s*)"[^"]*"', rf'\g<1>"{ip}"', text, count=1)
    cfg.write_text(text, encoding="utf-8")


def run_brand(job: dict, rows: list, brand: str, bi: int, serial: str,
              bundle_dir: Path, mark, add_log):
    """真机跑该品牌整列：复制 run 专属工作目录并注入台架 → 组装命令 → 委托 runner_common。

    Zcode 的设备注入是**改写包内 config.yaml**（文件级），多品牌/多 job 并发时共用
    缓存目录会互相覆盖注入 → 每次执行复制一份 run 专属目录（源码包很小，秒级），跑完即删。
    """
    import shutil
    import sys

    node_rows = _build_node_rows(bundle_dir, rows)     # 映射/收集用共享缓存目录（只读）

    workdir = bundle_dir.parent / f"run_{job['id']}_{bi}_zcode"
    shutil.copytree(bundle_dir, workdir, dirs_exist_ok=True)
    _inject_device(workdir, serial)

    progress_file = config.PROGRESS_DIR / f"{job['id']}_{bi}_zcode.jsonl"
    allure_dir = config.PROGRESS_DIR / f"allure_{job['id']}_{bi}"
    config.PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "JDO_PROGRESS": str(progress_file)}
    # -o addopts= 覆盖包 pytest.ini 里的 --clean-alluredir 等，改用平台 allure 目录
    # nodeid 按 node_rows 的插入顺序（= 收集顺序）传给 pytest，尊重框架 test_01→02→03 设计序
    cmd = [sys.executable, "-m", "pytest", *node_rows, "-q", "--color=no",
           "-o", "addopts=", "-p", "no:cacheprovider",
           "-p", runner_common.PLUGIN_FILENAME[:-3], "--alluredir", str(allure_dir)]

    add_log(f"› {brand}台架({serial}) 真机执行 Zcode(u2) · {len(node_rows)} 个测试覆盖 {len(rows)} 条用例")
    try:
        runner_common.track_pytest(job, rows, brand, bi, workdir, node_rows, cmd, env,
                                   mark, add_log, "zcode")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)     # run 专属目录用完即删
