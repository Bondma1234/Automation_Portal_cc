"""脚本管理接口：列表 / 上传 / 标记扫描 / 下载 / 框架脚手架。"""
import json
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from ..models import RunScriptBody
from ..services import official_service, run_service, script_service

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("")
def list_scripts():
    return script_service.list_scripts()


@router.post("/scan")
async def scan(file: UploadFile = File(...)):
    """只读扫描 .py/.zip 内的 @pytest.mark.case 标记（上传弹窗选完文件后自动勾选用）。"""
    content = await file.read()
    try:
        script_service.check_size(content)
        return {"cases": script_service.scan_case_marks(file.filename or "", content)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload(file: UploadFile = File(...), name: str = Form(...), app: str = Form(...),
                 version: str = Form("v1.0"), cases: str = Form("[]")):
    """cases 为 JSON 数组：[[case_id, module, priority], ...]（前端勾选结果，与原型一致）。

    自动识别框架来源：若为 Media_automation 包（含映射 CSV），走适配器按 CSV 映射覆盖率；
    否则走标准路径（按勾选建映射）。前端无需区分。
    """
    filename = file.filename or "script.py"
    content = await file.read()
    try:
        script_service.check_size(content)
        is_zip = filename.lower().endswith(".zip")
        if is_zip and official_service.is_zcode_bundle(content):
            saved = script_service.save_upload(filename, content)
            r = official_service.import_zcode_bundle(content, name.strip() or filename,
                                                     str(saved), orig_filename=filename)
            return {"id": r["script_id"], "saved": saved.name, "cases": r["mapped"],
                    "framework": "media_zcode",
                    "message": f"识别为 Zcode(u2) 包 · 按覆盖矩阵接入 {r['mapped']} 条用例"
                               + (f"（{r['unmatched']} 条未匹配官方库）" if r["unmatched"] else "")}
        if is_zip and official_service.is_media_bundle(content):
            saved = script_service.save_upload(filename, content)
            r = official_service.import_media_bundle(content, name.strip() or filename,
                                                     str(saved), orig_filename=filename)
            return {"id": r["script_id"], "saved": saved.name, "cases": r["mapped"],
                    "framework": "media_automation",
                    "message": f"识别为 Media_automation 包 · 按映射接入 {r['mapped']} 条用例"
                               + (f"（{r['unmatched']} 条未匹配官方库）" if r["unmatched"] else "")}
        picked = json.loads(cases)
        case_ids = [c[0] for c in picked]
        case_meta = {c[0]: (c[1], c[2]) for c in picked}
        return script_service.upload(filename, content, name.strip(), app,
                                     version.strip() or "v1.0", case_ids, case_meta)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scaffold/preview")
def scaffold_preview(fw: str = "jdo"):
    """框架预览（fw = jdo | zcode | media）：文件树 + 目录职责说明 + 下载指向。

    jdo 为平台标准脚手架；zcode / media 取该框架最新上传的 zip（未上传返回 404）。
    """
    try:
        return script_service.framework_preview(fw)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/scaffold")
def scaffold():
    """下载框架脚手架 zip：同事本地跑脚本所需的完整骨架（core/conftest/依赖/样例）。"""
    data = script_service.build_scaffold_zip()
    return Response(content=data, media_type="application/zip", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote('JDO框架脚手架.zip')}"})


@router.post("/{script_id}/run")
def run_script(script_id: int, body: RunScriptBody):
    """按脚本执行：直接跑该脚本对应框架的用例（脚本管理页「执行」入口）。"""
    try:
        job_id = run_service.start_script(script_id, body.brands)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    job = run_service.get_progress(job_id)
    return {"job": job_id, "rows": job["rows"], "brands": job["brands"], "total": job["total"]}


@router.get("/{script_id}/download")
def download(script_id: int):
    got = script_service.get_download(script_id)
    if not got:
        raise HTTPException(status_code=404, detail="脚本不存在")
    path, filename = got
    return FileResponse(path, filename=filename)
