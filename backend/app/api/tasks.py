"""测试任务接口：列表 / 新建。"""
from contextlib import closing

from fastapi import APIRouter

from .. import db
from ..models import TaskBody
from ..services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("")
def list_tasks():
    return task_service.list_tasks()


@router.post("")
def create_task(body: TaskBody):
    with closing(db.get_conn()) as conn:   # 全选判断需要 App 总数
        total_apps = conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
    return task_service.create_task(body.name.strip(), body.apps, body.brands,
                                    body.scope, body.mode, total_apps)
