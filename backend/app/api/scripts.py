"""脚本管理接口：列表 / 上传（多版本）/ 识别扫描 / 版本管理 / 下载 / 框架预览。"""
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from .. import config
from ..models import RunScriptBody
from ..services import official_service, run_service, script_service

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("")
def list_scripts():
    return script_service.list_scripts()


@router.post("/scan")
async def scan(file: UploadFile = File(...)):
    """上传弹窗选完文件后的只读识别摘要：框架类型 + 映射/标记命中统计，不落盘。"""
    filename = file.filename or ""
    content = await file.read()
    try:
        script_service.check_size(content)
        if filename.lower().endswith(".zip"):
            found = official_service.inspect_zip(content)
            if found:                              # Zcode / Media 包：映射来自包内 CSV/矩阵
                return {**found, "cases": [], "unmatched_ids": []}
        # jdo 路径：扫描 @pytest.mark.case 标记并与官方库比对
        _, matched, unmatched = script_service.snapshot_from_marks(filename, content)
        return {"framework": "jdo" if (matched or unmatched) else "",
                "matched": len(matched), "unmatched": len(unmatched),
                "cases": matched, "unmatched_ids": unmatched}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 上传结果 → 前端提示文案（多版本语义）
_ACTION_TEXT = {"created": "已创建脚本", "new_version": "已新增版本并设为当前",
                "overwritten": "已覆盖该版本"}


@router.post("/upload")
async def upload(file: UploadFile = File(...), name: str = Form(...), app: str = Form(...),
                 version: str = Form("v1.0")):
    """上传即自动映射（不再手工勾选用例）+ 多版本落库：

    同名脚本：新版本号=新增版本并激活；已有版本号=覆盖修复该版本。
    框架自动识别：Zcode / Media_automation 按包内映射，其余按 @pytest.mark.case 标记。
    """
    filename = file.filename or "script.py"
    content = await file.read()
    sname, ver = name.strip() or filename, version.strip() or "v1.0"
    try:
        script_service.check_size(content)
        is_zip = filename.lower().endswith(".zip")
        if is_zip and official_service.is_zcode_bundle(content):
            r = official_service.import_zcode_bundle(content, sname, ver, orig_filename=filename)
            fw_text = f"识别为 Zcode(u2) 包 · 按覆盖矩阵映射 {r['mapped']} 条用例"
        elif is_zip and official_service.is_media_bundle(content):
            r = official_service.import_media_bundle(content, sname, ver, orig_filename=filename)
            fw_text = f"识别为 Media_automation 包 · 按映射 CSV 接入 {r['mapped']} 条用例"
        else:
            snapshot, matched, unmatched = script_service.snapshot_from_marks(filename, content)
            r = script_service.save_version(sname, app, ver, config.FRAMEWORK_JDO,
                                            filename, content, snapshot)
            r["unmatched"] = len(unmatched)
            fw_text = (f"识别 {len(matched) + len(unmatched)} 条用例标记 · 命中官方库 {len(matched)} 条"
                       if (matched or unmatched) else "未识别到用例标记 · 不计入覆盖率")
        return {**r, "message": f"{_ACTION_TEXT.get(r['action'], '已保存')} {ver} · {fw_text}"
                                + (f"（{r['unmatched']} 条未匹配官方库）" if r.get("unmatched") else "")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- 版本管理：激活 / 删除 / 按版本下载 ----------------
@router.post("/{script_id}/versions/{version_id}/activate")
def activate_version(script_id: int, version_id: int):
    """把指定版本设为当前（覆盖率与执行随之切换到该版本）。"""
    try:
        script_service.activate_version(script_id, version_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.delete("/{script_id}/versions/{version_id}")
def delete_version(script_id: int, version_id: int):
    """删除某版本（至少保留一个；删当前版本时自动激活剩余最新版）。"""
    try:
        script_service.delete_version(script_id, version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/{script_id}/versions/{version_id}/download")
def download_version(script_id: int, version_id: int):
    got = script_service.get_version_download(script_id, version_id)
    if not got:
        raise HTTPException(status_code=404, detail="该版本无原件")
    path, filename = got
    return FileResponse(path, filename=filename)


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
        job_id = run_service.start_script(script_id, body.brands, body.device_ids)
    except run_service.DeviceBusyError as e:   # 台架被占用 → 明确拒绝
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    job = run_service.get_progress(job_id)
    return {"job": job_id, "rows": job["rows"], "brands": job["brands"], "total": job["total"]}


@router.get("/{script_id}/download")
def download(script_id: int):
    got = script_service.get_download(script_id)
    if not got:
        raise HTTPException(status_code=404, detail="脚本不存在")
    path, filename = got
    return FileResponse(path, filename=filename)
