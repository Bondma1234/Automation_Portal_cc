"""资源与系统接口：设备 / 应用 / 定时调度 / 系统设置 / 成员。"""
from fastapi import APIRouter, HTTPException

from ..models import AppBody, SettingsBody
from ..services import resource_service

router = APIRouter(prefix="/api", tags=["resources"])


@router.get("/devices")
def devices():
    return resource_service.list_devices()


@router.get("/apps")
def apps():
    return resource_service.list_apps()


@router.post("/apps")
def create_app(body: AppBody):
    try:
        resource_service.create_app(body.name.strip(), body.package.strip(),
                                    body.activity.strip(), body.version.strip(),
                                    body.account.strip())
    except ValueError as e:            # App 名重复
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/schedules")
def schedules():
    return resource_service.list_schedules()


@router.post("/schedules/{sid}/toggle")
def toggle_schedule(sid: int):
    try:
        return {"enabled": resource_service.toggle_schedule(sid)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/settings")
def get_settings():
    return resource_service.get_settings()


@router.put("/settings")
def save_settings(body: SettingsBody):
    resource_service.save_settings(body.webhook, body.notify_fail, body.notify_daily)
    return {"ok": True}


@router.get("/members")
def members():
    return resource_service.list_members()
