"""JDO 车机自动化测试平台 —— FastAPI 入口。

启动：cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8770
访问：http://127.0.0.1:8770 （后端同时托管 frontend/ 静态前端，天然同源无跨域）
⚠️ 端口 8765 被并行的 Codex 平台占用，本平台固定 8770。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api import all_routers


class NoCacheStaticFiles(StaticFiles):
    """前端静态文件禁用强缓存：免构建工程「改完刷新即生效」的保障。

    浏览器对 ES 模块有激进的内存缓存，改了 js 刷新页面可能仍跑旧代码；
    no-cache 要求每次向服务器校验（配合 ETag，未变仍走 304，开销可忽略）。
    """

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

app = FastAPI(title="JDO 车机自动化测试平台", version="0.2.0")

# 开发期允许跨域（前端也可独立起静态服务调试）；同源部署时不影响
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    db.init_db()   # 建库建表 + 首次种子数据（幂等）
    try:
        from .services import scanner
        scanner.sync_framework_scripts()   # 仓库框架脚本纳入覆盖率（无框架目录时为空操作）
    except Exception:
        pass   # 扫描失败不阻塞平台启动
    try:
        from .services import allure_service
        allure_service.warm_up()           # 预热历史报告的 Allure HTML（后台串行，不阻塞启动）
    except Exception:
        pass


for r in all_routers:
    app.include_router(r)

# Allure HTML 静态托管（须在 "/" 兜底挂载之前注册）：/allure/<报告id>/index.html
config.ALLURE_HTML_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/allure", StaticFiles(directory=config.ALLURE_HTML_DIR, html=True), name="allure")

# 静态前端挂在最后：/api/* 之外的路径都由前端接管（html=True 使 / 返回 index.html）
app.mount("/", NoCacheStaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
