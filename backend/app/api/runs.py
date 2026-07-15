"""执行中心接口：发起执行（立即返回 job）+ 进度轮询。"""
from fastapi import APIRouter, HTTPException

from ..models import RunBody
from ..services import run_service

router = APIRouter(prefix="/api/run", tags=["run"])


@router.post("")
def start_run(body: RunBody):
    """启动后台执行，立即返回 job_id 与矩阵行标签（前端先画格子再轮询点亮）。

    device_ids=点名台架（一台一列）；brands=模拟品牌列（或无 device_ids 时的旧品牌池路径）。
    """
    try:
        job_id = run_service.start(body.task, body.brands, body.device_ids)
    except run_service.DeviceBusyError as e:   # 台架被占用 → 明确拒绝，防并发打架
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:                    # 点名设备不可用等
        raise HTTPException(status_code=400, detail=str(e))
    job = run_service.get_progress(job_id)
    return {"job": job_id, "rows": job["rows"], "brands": job["brands"], "total": job["total"]}


@router.get("/active")
def active_jobs():
    """进行中的 job 列表：执行中心切走再回来 / 刷新页面时据此重连现场。"""
    return run_service.list_active()


@router.get("/{job_id}/progress")
def progress(job_id: str):
    job = run_service.get_progress(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job 不存在（平台可能已重启）")
    return job


@router.post("/{job_id}/stop")
def stop(job_id: str):
    """请求终止执行：置停止标志，执行线程随即 kill pytest；剩余用例记「未执行」。"""
    if not run_service.stop_job(job_id):
        raise HTTPException(status_code=404, detail="job 不存在或已结束")
    return {"ok": True}
