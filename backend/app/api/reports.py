"""测试报告接口：筛选查询（含明细）/ 导出 Excel / Allure 报告。"""
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from ..services import allure_service, report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(date_from: str = "", date_to: str = "", app: str = "",
                 brand: str = "", status: str = ""):
    return report_service.list_reports(date_from, date_to, app, brand, status)


@router.delete("/{report_id}")
def delete_report(report_id: int):
    """删除报告（主记录 + 用例明细 + Allure 产物），不可恢复。"""
    try:
        report_service.delete_report(report_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.get("/{report_id}/allure")
def allure_report(report_id: int):
    """确保该报告的 Allure HTML 已生成（惰性，首次约 5~15s），返回访问地址。"""
    try:
        return {"url": allure_service.ensure_html(report_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export")
def export(date_from: str = "", date_to: str = "", app: str = "",
           brand: str = "", status: str = ""):
    data = report_service.export_excel(date_from=date_from, date_to=date_to,
                                       app=app, brand=brand, status=status)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('测试报告.xlsx')}"})
