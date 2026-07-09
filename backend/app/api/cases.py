"""测试用例接口：查询 / 新增 / Excel 导入（支持 dry_run 预览）/ 导出 / 模板。"""
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from ..models import CaseBody
from ..services import case_service, official_service

router = APIRouter(prefix="/api/cases", tags=["cases"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(data: bytes, filename: str) -> Response:
    """xlsx 下载响应；filename* 用 UTF-8 百分号编码支持中文文件名。"""
    return Response(content=data, media_type=_XLSX, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.get("")
def list_cases(app: str = "", priority: str = "", status: str = ""):
    return case_service.list_cases(app, priority, status)


@router.post("")
def create_case(body: CaseBody):
    try:
        case_service.create_case(body.id.strip(), body.app, body.module.strip(), body.priority)
    except ValueError as e:            # 编号重复
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/import")
async def import_cases(file: UploadFile = File(...), dry_run: int = 0):
    """dry_run=1：仅解析统计（导入弹窗选完文件后的预览）；=0：真正落库。"""
    content = await file.read()
    try:
        return case_service.import_excel(content, dry_run=bool(dry_run))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Excel 解析失败，请检查文件格式")


@router.post("/import-official")
async def import_official(file: UploadFile = File(...), replace: int = 1):
    """官方测试报告 Excel → 手工用例库（覆盖率分母）。replace=1 整库替换种子数据。"""
    content = await file.read()
    try:
        return official_service.import_official_cases(content, replace=bool(replace))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
def export_cases(app: str = "", priority: str = "", status: str = ""):
    return _xlsx_response(case_service.export_excel(app, priority, status), "功能用例清单.xlsx")


@router.get("/template")
def template():
    return _xlsx_response(case_service.template_excel(), "用例导入模板.xlsx")
