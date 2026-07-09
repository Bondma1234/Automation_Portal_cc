"""健康检查 + 前端公共元数据（App/品牌下拉选项来源）。"""
from contextlib import closing

from fastapi import APIRouter

from .. import config, db

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def meta():
    """前端启动时拉一次：App 列表 + 全部品牌 + 有台架的品牌（任务/执行的可选品牌）。"""
    with closing(db.get_conn()) as conn:
        apps = [r["name"] for r in conn.execute("SELECT name FROM apps ORDER BY id")]
        device_brands = [r["brand"] for r in conn.execute(
            "SELECT DISTINCT brand FROM devices ORDER BY id")]
    return {"apps": apps, "brands": config.BRANDS, "device_brands": device_brands}
