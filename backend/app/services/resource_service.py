"""资源与系统模块业务逻辑：设备 / 应用 / 定时调度 / 系统设置 / 成员。

设备是执行的单一事实源：devices 表的 udid 即 adb serial，ip:port 格式的
进入该品牌的「真机执行池」（run_service 按品牌从池里分配空闲台架，
执行中心也可按 device_id 点名执行）。
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing

from .. import config, db


# ---------------- 设备 ----------------
def list_devices() -> list:
    """台架列表（online/agent_ready/meta 为上次探活回写的状态，「刷新」触发 probe_devices）。"""
    with closing(db.get_conn()) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM devices ORDER BY id")]
    for r in rows:
        try:
            r["meta"] = json.loads(r.get("meta") or "{}")
        except (TypeError, ValueError):
            r["meta"] = {}
    return rows


def get_devices(device_ids: list) -> list:
    """按 id 取台架（执行中心按设备执行用），保持传入顺序。"""
    if not device_ids:
        return []
    ph = ",".join("?" * len(device_ids))
    with closing(db.get_conn()) as conn:
        rows = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT * FROM devices WHERE id IN ({ph})", device_ids)}
    return [rows[i] for i in device_ids if i in rows]


def brand_pool() -> dict:
    """执行设备池：brand → [udid,...]。只收 ip:port 格式的真台架（演示占位不进池）。"""
    pool = {}
    with closing(db.get_conn()) as conn:
        for r in conn.execute("SELECT brand, udid FROM devices WHERE udid LIKE '%:%' ORDER BY id"):
            pool.setdefault(r["brand"], []).append(r["udid"])
    return pool


def _sh(udid: str, *args: str, timeout: int = 6) -> str:
    try:
        p = subprocess.run(["adb", "-s", udid, *args], capture_output=True, timeout=timeout)
        return p.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _probe_one(udid: str) -> tuple:
    """单台探活（只读，不改设备状态）：online / root / 富信息 meta。

    root 是 u2 自动化的硬前提（SELinux 拦自动化端口，见 config 注释），
    这里只探测不主动 root —— 主动 root 会重启 adbd，交给执行前的 _probe_device 做。
    meta（在线才采）：型号 / API / locale / 被测 App 版本，设备卡片与执行中心展示用。
    """
    online = root = 0
    meta = {}
    try:
        if ":" in udid:
            subprocess.run(["adb", "connect", udid], capture_output=True, timeout=6)
        online = int(_sh(udid, "get-state") == "device")
        if online:
            root = int("uid=0" in _sh(udid, "shell", "id"))
            meta = {
                "model": _sh(udid, "shell", "getprop", "ro.product.model"),
                "api": _sh(udid, "shell", "getprop", "ro.build.version.sdk"),
                "android": _sh(udid, "shell", "getprop", "ro.build.version.release"),
                "locale": _sh(udid, "shell", "getprop", "persist.sys.locale"),
            }
            # ⚠ 管道命令必须整体作为一个 shell 参数（adb 多参数拼接丢引号分组）
            vd = _sh(udid, "shell",
                     f"dumpsys package {config.PREFLIGHT_APP['package']} | grep versionName",
                     timeout=15)
            m = re.search(r"versionName=(\S+)", vd)
            if m:
                meta["app_version"] = m.group(1)
    except Exception:
        pass
    return online, root, meta


def probe_devices() -> list:
    """并行探活全部台架并回写 online/agent_ready/meta，返回最新列表（设备页「刷新」）。"""
    with closing(db.get_conn()) as conn:
        rows = [dict(r) for r in conn.execute("SELECT id, udid FROM devices")]
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_probe_one, r["udid"]): r["id"] for r in rows}
        for f in as_completed(futs):
            results[futs[f]] = f.result()
    with closing(db.get_conn()) as conn:
        for did, (online, root, meta) in results.items():
            conn.execute("UPDATE devices SET online = ?, agent_ready = ?, meta = ? WHERE id = ?",
                         (online, root, json.dumps(meta, ensure_ascii=False), did))
        conn.commit()
    return list_devices()


def create_device(name: str, brand: str, udid: str, resolution: str, os_ver: str):
    """接入新台架；udid 重复抛 ValueError。入库即进该品牌执行池（ip:port 格式）。"""
    with closing(db.get_conn()) as conn:
        if conn.execute("SELECT 1 FROM devices WHERE udid = ?", (udid,)).fetchone():
            raise ValueError("该台架地址（udid）已接入")
        conn.execute(
            "INSERT INTO devices(name,brand,udid,resolution,os,online,agent_ready)"
            " VALUES(?,?,?,?,?,0,0)",
            (name, brand, udid, resolution or "—", os_ver or "—"))
        conn.commit()
    probe_devices()          # 接入后立即探一次，回写真实在线状态


def delete_device(device_id: int):
    with closing(db.get_conn()) as conn:
        if not conn.execute("SELECT 1 FROM devices WHERE id = ?", (device_id,)).fetchone():
            raise ValueError("台架不存在")
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        conn.commit()


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
