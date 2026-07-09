"""资源与系统模块业务逻辑：设备 / 应用 / 定时调度 / 系统设置 / 成员。"""
from contextlib import closing

from .. import db


# ---------------- 设备 ----------------
def list_devices() -> list:
    """台架列表。真机探活（adb devices / atx-agent 健康检查）在接入真实台架时补充：
    按 udid 匹配到在线序列号则回写 online/agent_ready，种子演示数据不受影响。"""
    with closing(db.get_conn()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM devices ORDER BY id")]


# ---------------- 应用 ----------------
def list_apps() -> list:
    """被测 App 登记表；「用例」列实时统计 cases 表，不落库。"""
    with closing(db.get_conn()) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM apps ORDER BY id")]
        for r in rows:
            r["case_count"] = conn.execute(
                "SELECT COUNT(*) FROM cases WHERE app = ?", (r["name"],)).fetchone()[0]
    return rows


def create_app(name: str, package: str, activity: str, version: str, account: str):
    """接入新被测 App；App 名重复时抛 ValueError（前端 toast）。"""
    with closing(db.get_conn()) as conn:
        if conn.execute("SELECT 1 FROM apps WHERE name = ?", (name,)).fetchone():
            raise ValueError("App 名称已存在")
        conn.execute(
            "INSERT INTO apps(name,package,activity,version,account) VALUES(?,?,?,?,?)",
            (name, package, activity or "—", version or "—", account or "—"))
        conn.commit()


# ---------------- 定时调度 ----------------
def list_schedules() -> list:
    with closing(db.get_conn()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM schedules ORDER BY id")]


def toggle_schedule(sid: int) -> bool:
    """启停开关：翻转 enabled 并持久化，返回新状态。真正的 cron 触发接 APScheduler 时实现。"""
    with closing(db.get_conn()) as conn:
        row = conn.execute("SELECT enabled FROM schedules WHERE id = ?", (sid,)).fetchone()
        if not row:
            raise ValueError("计划不存在")
        new = 0 if row["enabled"] else 1
        conn.execute("UPDATE schedules SET enabled = ? WHERE id = ?", (new, sid))
        conn.commit()
        return bool(new)


# ---------------- 系统设置 ----------------
def get_settings() -> dict:
    with closing(db.get_conn()) as conn:
        kv = {r["key"]: r["value"] for r in conn.execute("SELECT * FROM settings")}
    return {"webhook": kv.get("webhook", ""),
            "notify_fail": kv.get("notify_fail") == "1",
            "notify_daily": kv.get("notify_daily") == "1"}


def save_settings(webhook: str, notify_fail: bool, notify_daily: bool):
    with closing(db.get_conn()) as conn:
        for k, v in (("webhook", webhook),
                     ("notify_fail", "1" if notify_fail else "0"),
                     ("notify_daily", "1" if notify_daily else "0")):
            conn.execute("INSERT INTO settings(key,value) VALUES(?,?)"
                         " ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        conn.commit()


def list_members() -> list:
    with closing(db.get_conn()) as conn:
        return [{"name": r["name"], "role": r["role"]}
                for r in conn.execute("SELECT * FROM users ORDER BY id")]


def check_login(username: str, password: str):
    """最简登录校验（原型阶段）；返回用户信息或 None。正式接 JWT 时替换此处。"""
    with closing(db.get_conn()) as conn:
        row = conn.execute("SELECT name, role FROM users WHERE username=? AND password=?",
                           (username, password)).fetchone()
        return dict(row) if row else None
