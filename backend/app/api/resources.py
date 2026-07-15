"""资源与系统接口：设备 / 应用 / 定时调度 / 系统设置 / 成员。"""
from fastapi import APIRouter, HTTPException

from ..models import AppBody, DeviceBody, SettingsBody
from ..services import resource_service

router = APIRouter(prefix="/api", tags=["resources"])


@router.get("/devices")
def devices():
    return resource_service.list_devices()


@router.post("/devices")
def create_device(body: DeviceBody):
    """接入台架：入库即进该品牌执行池（udid 为 ip:5555 时），并立即探活一次。"""
    try:
        resource_service.create_device(body.name.strip(), body.brand.strip(),
                                       body.udid.strip(), body.resolution.strip(),
                                       body.os.strip())
    except ValueError as e:            # udid 重复
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/devices/probe")
def probe_devices():
    """并行探活全部台架（adb 可达 + root 状态）并回写，返回最新列表。"""
    return resource_service.probe_devices()


@router.delete("/devices/{device_id}")
def delete_device(device_id: int):
    try:
        resource_service.delete_device(device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


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
