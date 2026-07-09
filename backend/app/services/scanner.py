"""框架脚本扫描器：让「仓库里的脚本」自动纳入覆盖率（不需要任何人工登记）。

原理：扫描 framework/testcases/**/test_*.py 里的 @pytest.mark.case("编号") 标记，
把每个测试文件 upsert 为一条「仓库脚本」（scripts 表，version=仓库，file_path=框架内路径），
并重建其用例映射（script_case）。文件删除后同步移除对应记录。

由此覆盖率的三类分子来源统一收口到 script_case 一张表：
    种子演示脚本 / 平台上传脚本 / 仓库框架脚本（本扫描器）
触发时机：服务启动 + 每次 GET /api/coverage（目录小，全量重扫成本可忽略）。
"""
import re
from contextlib import closing
from datetime import datetime

from .. import config, db

# 用例标记（与 conftest/规范一致）；只扫 test_*.py，与 pytest 收集规则对齐
_MARK_RE = re.compile(r"@pytest\.mark\.case\(\s*[\"']([^\"']+)[\"']\s*\)")

# 框架模块目录名 -> 所属 App（脚本框架规范的目录约定）
MODULE_APP = {
    "kuwo": "酷我音乐", "ximalaya": "喜马拉雅", "leting": "乐听",
    "iqiyi": "爱奇艺", "launcher": "Launcher", "meeting": "车内会议",
}


def scan_framework() -> dict:
    """返回 {文件绝对路径: {"name":.., "app":.., "case_ids":[...]}}；无框架目录返回空。"""
    tc_dir = config.FRAMEWORK_DIR / "testcases"
    found = {}
    if not tc_dir.is_dir():
        return found
    for path in sorted(tc_dir.rglob("test_*.py")):
        case_ids = _MARK_RE.findall(path.read_text(encoding="utf-8", errors="replace"))
        if not case_ids:
            continue          # 没有标记的文件不计入覆盖率（规范规则①）
        module_dir = path.parent.name
        found[str(path)] = {
            "name": path.stem,
            "app": MODULE_APP.get(module_dir, module_dir),
            "case_ids": list(dict.fromkeys(case_ids)),   # 去重保序
        }
    return found


def sync_framework_scripts():
    """把扫描结果与 scripts 表对账（幂等）：新增/更新/删除「仓库脚本」记录。"""
    found = scan_framework()
    prefix = str(config.FRAMEWORK_DIR)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(db.get_conn()) as conn:
        existing = {r["file_path"]: r["id"] for r in conn.execute(
            "SELECT id, file_path FROM scripts WHERE file_path LIKE ?", (prefix + "%",))}

        # 文件已删除 -> 移除脚本与映射
        for path, sid in existing.items():
            if path not in found:
                conn.execute("DELETE FROM script_case WHERE script_id = ?", (sid,))
                conn.execute("DELETE FROM scripts WHERE id = ?", (sid,))

        # 新增/更新 + 重建映射（module/priority 快照从 cases 表回查，查不到留空）
        for path, info in found.items():
            if path in existing:
                sid = existing[path]
                conn.execute("UPDATE scripts SET name=?, app=? WHERE id=?",
                             (info["name"], info["app"], sid))
            else:
                sid = conn.execute(
                    "INSERT INTO scripts(name,app,version,framework,file_name,file_path,last_result,created_at)"
                    " VALUES(?,?,'仓库',?,?,?,'pending',?)",
                    (info["name"], info["app"], config.FRAMEWORK_JDO,
                     path.rsplit("\\", 1)[-1], path, ts)).lastrowid
            conn.execute("DELETE FROM script_case WHERE script_id = ?", (sid,))
            for cid in info["case_ids"]:
                row = conn.execute("SELECT module, priority FROM cases WHERE id = ?", (cid,)).fetchone()
                conn.execute(
                    "INSERT INTO script_case(script_id,case_id,module,priority) VALUES(?,?,?,?)",
                    (sid, cid, row["module"] if row else "", row["priority"] if row else ""))
        conn.commit()
