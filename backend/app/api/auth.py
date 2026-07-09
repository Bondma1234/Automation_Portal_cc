"""登录（原型阶段：账号密码最简校验；预留 JWT 升级位）。"""
from fastapi import APIRouter, HTTPException

from ..models import LoginBody
from ..services import resource_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginBody):
    user = resource_service.check_login(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return {"ok": True, "user": user}
