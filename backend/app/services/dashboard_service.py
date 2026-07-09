"""工作台聚合数据：指标卡 + 最近执行。"""
from contextlib import closing
from datetime import datetime, timedelta

from .. import db
from . import coverage_service


def _time_label(t: str, now: datetime) -> str:
    """最近执行的时间展示（与原型一致）：今天只显时分，昨天加「昨日」，更早显月-日。"""
    date, _, hm = t.partition(" ")
    if date == now.strftime("%Y-%m-%d"):
        return hm
    if date == (now - timedelta(days=1)).strftime("%Y-%m-%d"):
        return f"昨日 {hm}"
    return f"{date[5:]} {hm}"


def summary() -> dict:
    now = datetime.now()
    cov = coverage_service.summary()
    with closing(db.get_conn()) as conn:
        today_runs = conn.execute("SELECT COUNT(*) FROM reports WHERE substr(time,1,10) = ?",
                                  (now.strftime("%Y-%m-%d"),)).fetchone()[0]
        # 执行成功率：最近 20 条报告的用例级通过率（比报告级更平滑）
        row = conn.execute("SELECT SUM(pass), SUM(total) FROM"
                           " (SELECT pass, total FROM reports ORDER BY id DESC LIMIT 20)").fetchone()
        success = round(row[0] / row[1] * 100) if row and row[1] else 0
        online = conn.execute("SELECT COUNT(*) FROM devices WHERE online = 1").fetchone()[0]
        total_dev = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        recent = [{"task": r["task"], "brand": r["brand"], "status": r["status"],
                   "time": _time_label(r["time"], now)}
                  for r in conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 4")]
    return {
        "coverage": cov["coverage"],
        "today_runs": today_runs,
        "success_rate": success,
        "devices": f"{online} / {total_dev}",
        "recent": recent,
    }
