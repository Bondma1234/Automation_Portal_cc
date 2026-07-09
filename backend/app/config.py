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
# 品牌 → 台架序列号：执行时该品牌若 adb 可达则真跑 pytest，否则自动回退模拟演示。
# .32 = 许可有效的 Audi 台架（2026-07-06 三条酷我用例真机 PASSED）；
# .89 = P0 主台架，媒体中心许可证过期待续期，续期后可加回。
# ⚠ 此固件用 SELinux 包策略拦截自动化端口(9008等)，adbd 必须为 root（探测时自动 adb root）。
REAL_DEVICE_MAP = {
    "奥迪": "192.168.2.32:5555",
}
PROGRESS_DIR = DATA_DIR / "progress"     # 真机执行的进度 jsonl（框架 conftest 回写）
COLLECT_TIMEOUT = 60                     # 预收集（--collect-only）超时（秒）
REAL_RUN_TIMEOUT = 600                   # 单品牌 pytest 会话超时（秒）

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
