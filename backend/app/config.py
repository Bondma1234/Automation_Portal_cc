"""全局配置：路径、服务端口、业务常量。

分层约定：
    api/       路由层 —— 只做参数接收与响应包装，不写业务逻辑
    services/  业务层 —— 全部业务规则在这里，可单测
    db.py      数据层 —— SQLite 连接、建表、种子数据
"""
from pathlib import Path

# ---------- 路径 ----------
BASE_DIR = Path(__file__).resolve().parent.parent      # backend/
PROJECT_ROOT = BASE_DIR.parent                          # Claude/（项目根）
DATA_DIR = BASE_DIR / "data"                            # SQLite 与上传文件
UPLOAD_DIR = DATA_DIR / "uploads"                       # 脚本原件（供下载）
DB_PATH = DATA_DIR / "jdo.db"                           # 删除此文件可重建种子库
FRONTEND_DIR = PROJECT_ROOT / "frontend"                # 免构建静态前端
FRAMEWORK_DIR = PROJECT_ROOT / "framework"              # pytest 测试框架（脚本作者产出）

# ---------- 服务 ----------
HOST = "0.0.0.0"
# ⚠️ 8765 被父目录下 Codex 工作区的另一套平台占用，本平台固定 8770，勿改。
PORT = 8770

# ---------- 业务常量（与原型一致） ----------
# 品牌矩阵：设备按品牌注册，执行/覆盖率按品牌维度展开
BRANDS = ["奥迪", "保时捷", "大众", "宝马", "奔驰"]

# App 全名 -> 矩阵短名（执行矩阵行标签用，如「酷我·播放控制」）
APP_SHORT = {
    "酷我音乐": "酷我", "喜马拉雅": "喜马", "乐听": "乐听",
    "爱奇艺": "爱奇艺", "Launcher": "Launcher", "车内会议": "会议",
}

# 官方测试报告 Excel 的 app sheet 名 -> (平台 App 全名, 用例编号前缀)
# 用例编号 = 前缀-4位序号（如 KW-0001），供各框架的映射引用；公共表结构异常不导入。
OFFICIAL_APP_SHEETS = {
    "酷我": ("酷我音乐", "KW"),
    "喜马拉雅": ("喜马拉雅", "XM"),
    "乐听": ("乐听", "LT"),
    "爱奇艺": ("爱奇艺", "IQ"),
}

# 框架标识
FRAMEWORK_JDO = "jdo_framework"          # 我们的 framework/（@pytest.mark.case 标记）
FRAMEWORK_MEDIA = "media_automation"     # Media_automation 包（docs CSV 映射，ADB-XML 驱动）
FRAMEWORK_ZCODE = "media_zcode"          # Media_automation_Zcode 包（markdown 映射，u2 驱动）

# 预估节省人力：每条自动化用例按人工执行 10 分钟折算，8 小时 = 1 人天
MANUAL_MINUTES_PER_CASE = 10
WORK_MINUTES_PER_DAY = 480

# ---------- 真机执行 ----------
# 真机台架由 devices 表驱动（brand → 台架池，udid 即 adb serial；「设备管理→接入台架」维护）。
# 旧 REAL_DEVICE_MAP 硬编码已废弃 —— 单一事实源收口数据库，接新台架无需改代码。
# 执行时该品牌池内若有可达且空闲的台架则真跑 pytest；无台架回退模拟；有台架但全被占用则拒绝启动。
# ⚠ 此固件用 SELinux 包策略拦截自动化端口(9008等)，adbd 必须为 root（探测时自动 adb root）。
PROGRESS_DIR = DATA_DIR / "progress"     # 真机执行的进度 jsonl（框架 conftest 回写）
COLLECT_TIMEOUT = 60                     # 预收集（--collect-only）超时（秒）
REAL_RUN_TIMEOUT = 600                   # 单品牌 pytest 会话超时下限（秒）
REAL_RUN_PER_TEST = 120                  # 每测试超时预算（media ADB-XML 慢，按量给时）
REAL_RUN_MAX = 3600                      # 单品牌会话超时上限：max(下限, 测试数×预算) 后封顶

# ---------- 环境预检（真机列执行前，借鉴 Codex 平台设计） ----------
# 被测 App 前台检查的目标：三套框架的被测对象都是 One Info 酷我模块
PREFLIGHT_APP = {"package": "com.jidouauto.media",
                 "component": "com.jidouauto.media/.ui.kuwo.main.KuwoMainActivity",
                 "action": "com.jidouauto.media.kuwo.LAUNCH_INTENT"}
# 前台等待预算：台架劣化时酷我冷启动实测可达 45s+（2026-07-13），给足 90s 免误判
PREFLIGHT_FOREGROUND_TIMEOUT = 90

# ---------- Allure 报告 ----------
# 真机执行：pytest --alluredir 产出结果；模拟/种子报告：点击时按报告明细合成结果 JSON。
# HTML 惰性生成（首次点击 5~15s），生成后永久缓存；由 /allure/<报告id>/ 静态托管。
ALLURE_RESULTS_DIR = PROJECT_ROOT / "reports" / "allure-results"   # 每报告一个结果目录
ALLURE_HTML_DIR = PROJECT_ROOT / "reports" / "allure-html"         # 每报告一个 HTML 目录
ALLURE_GENERATE_TIMEOUT = 120            # allure generate 超时（秒，Java 冷启动较慢）

# 脚本上传大小上限（MB）：防止大文件整包读入内存拖垮服务
MAX_UPLOAD_MB = 50

# 登录（原型阶段为最简校验，后续可替换为 JWT，见 api/auth.py）
DEFAULT_ADMIN = ("admin", "123456")
