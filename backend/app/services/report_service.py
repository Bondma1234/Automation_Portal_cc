"""测试报告业务逻辑：筛选查询 / 详情 / 导出 / 删除。"""
import io
from contextlib import closing

from openpyxl import Workbook

from .. import db


def delete_report(report_id: int):
    """删除报告：主记录 + 用例明细 + Allure 产物（真机报告附件占磁盘，一并清理）。

    不可恢复；不存在抛 ValueError（API 层转 404）。工作台/统计实时聚合 reports 表，
    删除后自然重算，无悬空引用（覆盖率/脚本最近结果均不依赖本表）。
    """
    with closing(db.get_conn()) as conn:
        if not conn.execute("SELECT 1 FROM reports WHERE id = ?", (report_id,)).fetchone():
            raise ValueError("报告不存在")
        conn.execute("DELETE FROM report_cases WHERE report_id = ?", (report_id,))
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        conn.commit()
    from . import allure_service              # 局部导入避免环依赖
    allure_service.purge(report_id)


def list_reports(date_from: str = "", date_to: str = "", app: str = "",
                 brand: str = "", status: str = "") -> list:
    """按 日期范围 / App / 品牌 / 状态 筛选，附带用例明细（行展开用）。

    App 筛选口径与原型一致：「多 App」的汇总报告在任何 App 筛选下都保留。
    """
    sql, args = "SELECT * FROM reports", []
    cond = []
    if date_from:
        cond.append("substr(time, 1, 10) >= ?"); args.append(date_from)
    if date_to:
        cond.append("substr(time, 1, 10) <= ?"); args.append(date_to)
    if app and app != "全部 App":
        cond.append("(app = ? OR app = '多 App')"); args.append(app)
    if brand and brand != "全部品牌":
        cond.append("brand = ?"); args.append(brand)
    if status and status != "全部状态":
        cond.append("status = ?"); args.append(status)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY id DESC"

    with closing(db.get_conn()) as conn:
        rows = [dict(r) for r in conn.execute(sql, args)]
        for r in rows:
            r["cases"] = [dict(c) for c in conn.execute(
                "SELECT case_id, name, result FROM report_cases WHERE report_id = ? ORDER BY rowid",
                (r["id"],))]
    return rows


def export_excel(**filters) -> bytes:
    """导出当前筛选的报告列表为 .xlsx。"""
    rows = list_reports(**filters)
    wb = Workbook()
    ws = wb.active
    ws.title = "测试报告"
    ws.append(["编号", "任务", "App", "品牌", "通过", "总数", "耗时", "结果", "时间", "触发"])
    for r in rows:
        ws.append([f"#{r['id']}", r["task"], r["app"], r["brand"], r["pass"],
                   r["total"], r["dur"], r["status"], r["time"], r["trigger_type"]])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
