"""覆盖率看板接口：一次返回 指标卡 + 趋势 + 热力矩阵。

每次请求前先同步框架仓库脚本的 @pytest.mark.case 标记 ——
保证「脚本写完提交进仓库，覆盖率立即可见」，无需任何人工登记。
"""
from fastapi import APIRouter

from ..services import coverage_service, scanner

router = APIRouter(prefix="/api", tags=["coverage"])


@router.get("/coverage")
def coverage():
    scanner.sync_framework_scripts()
    return {"summary": coverage_service.summary(),
            "trend": coverage_service.trend(),
            "heatmap": coverage_service.heatmap()}
