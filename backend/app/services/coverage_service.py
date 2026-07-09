"""覆盖率业务逻辑（口径见需求文档 2.2，指标待用户定稿，先按已确认口径实现）。

- 主指标：业务用例覆盖率 = 已自动化用例 ÷ 全部手工用例；
- 分子：script_case 中存在映射、且在 cases 表中的用例（自动判定，不人工填写）；
- 派生：预估节省人力 = 已自动化 × 单条人工耗时 × 有台架的品牌数 ÷ 每日工时。
"""
from contextlib import closing

from .. import config, db


def summary() -> dict:
    """覆盖率指标卡：分母 / 分子 / 覆盖率% / 预估节省人力（人天/版）。

    官方库为 P1~P4 全量，团队自动化重点是 P1/P2，故额外给出 P1/P2 口径，
    前端可展示更有意义的重点覆盖率。
    """
    with closing(db.get_conn()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        automated = conn.execute(
            "SELECT COUNT(DISTINCT c.id) FROM cases c JOIN script_case sc ON sc.case_id = c.id"
        ).fetchone()[0]
        p12_total = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE priority IN ('P1','P2')").fetchone()[0]
        p12_auto = conn.execute(
            "SELECT COUNT(DISTINCT c.id) FROM cases c JOIN script_case sc ON sc.case_id = c.id"
            " WHERE c.priority IN ('P1','P2')").fetchone()[0]
        device_brands = conn.execute("SELECT COUNT(DISTINCT brand) FROM devices").fetchone()[0]
    coverage = round(automated / total * 100) if total else 0
    p12_coverage = round(p12_auto / p12_total * 100) if p12_total else 0
    saved = round(automated * config.MANUAL_MINUTES_PER_CASE * device_brands
                  / config.WORK_MINUTES_PER_DAY, 1)
    return {"total": total, "automated": automated, "coverage": coverage, "saved_days": saved,
            "p12_total": p12_total, "p12_automated": p12_auto, "p12_coverage": p12_coverage}


def trend() -> list:
    """覆盖率增长趋势：历史版本快照 + 「当前」实时点。"""
    with closing(db.get_conn()) as conn:
        rows = [{"version": r["version"], "coverage": r["coverage"]}
                for r in conn.execute("SELECT * FROM coverage_trend ORDER BY rowid")]
    rows.append({"version": "当前", "coverage": summary()["coverage"]})
    return rows


def heatmap() -> dict:
    """App × 品牌 覆盖矩阵。

    单格口径：该 App 的自动化覆盖率%；品牌无台架时记 0（前端渲染为「—」），
    因为没有设备就无法在该品牌上执行自动化。
    """
    with closing(db.get_conn()) as conn:
        apps = [r["name"] for r in conn.execute("SELECT name FROM apps ORDER BY id")]
        device_brands = {r["brand"] for r in conn.execute("SELECT DISTINCT brand FROM devices")}
        matrix = []
        for app in apps:
            total = conn.execute("SELECT COUNT(*) FROM cases WHERE app = ?", (app,)).fetchone()[0]
            automated = conn.execute(
                "SELECT COUNT(DISTINCT c.id) FROM cases c JOIN script_case sc ON sc.case_id = c.id"
                " WHERE c.app = ?", (app,)).fetchone()[0]
            cov = round(automated / total * 100) if total else 0
            matrix.append([cov if b in device_brands else 0 for b in config.BRANDS])
    return {"apps": apps, "brands": config.BRANDS, "matrix": matrix}
