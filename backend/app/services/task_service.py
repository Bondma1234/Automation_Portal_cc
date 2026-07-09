"""测试任务业务逻辑：把用例组合成回归套件（App 范围 × 品牌范围）。"""
import json
from contextlib import closing
from datetime import datetime

from .. import db

# 全名 -> 任务列表展示用短名（与原型种子文案「酷我 / 喜马 / 爱奇艺」一致）
_LABEL_SHORT = {"酷我音乐": "酷我", "喜马拉雅": "喜马"}


def list_tasks() -> list:
    """任务列表，新建的排最前（对应原型 unshift 行为）。"""
    with closing(db.get_conn()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id DESC")]


def create_task(name: str, apps: list, brands: list, scope: str, mode: str, total_apps: int) -> dict:
    """新建任务。

    - 展示文案与原型一致：全选 App 显示「全部 N App」，否则全名以「 / 」相连；
    - 预估用例数与原型同口径：App 数 × 品牌数 × 约 5 条。
    """
    apps_label = f"全部 {total_apps} App" if len(apps) >= total_apps else " / ".join(apps)
    brands_label = " / ".join(brands)
    count = len(apps) * len(brands) * 5
    with closing(db.get_conn()) as conn:
        cur = conn.execute(
            "INSERT INTO tasks(name,apps_label,brands_label,apps_json,brands_json,scope,mode,case_count,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (name, apps_label, brands_label,
             json.dumps(apps, ensure_ascii=False), json.dumps(brands, ensure_ascii=False),
             scope, mode, count, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return {"id": cur.lastrowid, "count": count}


def get_task(name: str):
    """按任务名取任务（执行中心按名称选任务，与原型下拉一致）。"""
    with closing(db.get_conn()) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE name = ? ORDER BY id DESC", (name,)).fetchone()
        return dict(row) if row else None
