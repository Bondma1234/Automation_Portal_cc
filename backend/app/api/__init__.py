"""路由层汇总：main.py 只需 include 这里的 all_routers。

约定：路由层只做「参数接收 → 调 service → 包装响应」，业务规则一律写在 services/。
"""
from . import auth, cases, coverage, dashboard, meta, reports, resources, runs, scripts, tasks

all_routers = [
    meta.router, auth.router, dashboard.router, cases.router, scripts.router,
    tasks.router, runs.router, reports.router, coverage.router, resources.router,
]
