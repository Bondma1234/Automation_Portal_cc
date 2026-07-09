"""工作台聚合接口。"""
from fastapi import APIRouter

from ..services import dashboard_service

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    return dashboard_service.summary()
