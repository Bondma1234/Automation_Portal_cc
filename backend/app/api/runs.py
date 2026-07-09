"""执行中心接口：发起执行（立即返回 job）+ 进度轮询。"""
from fastapi import APIRouter, HTTPException

from ..models import RunBody
from ..services import run_service

router = APIRouter(prefix="/api/run", tags=["run"])


@router.post("")
def start_run(body: RunBody):
    """启动后台执行，立即返回 job_id 与矩阵行标签（前端先画格子再轮询点亮）。"""
    job_id = run_service.start(body.task, body.brands)
    job = run_service.get_progress(job_id)
    return {"job": job_id, "rows": job["rows"], "brands": job["brands"], "total": job["total"]}


@router.get("/{job_id}/progress")
def progress(job_id: str):
    job = run_service.get_progress(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job 不存在（平台可能已重启）")
    return job
