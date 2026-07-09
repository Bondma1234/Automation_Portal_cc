"""数据层：SQLite 连接、建表、种子数据。

约定：
- 每次调用 get_conn() 返回一个新连接（FastAPI 同步端点跑在线程池，连接不跨线程共享）；
- 行工厂设为 sqlite3.Row，服务层可按列名取值；
- 首次启动自动建表并灌入与原型完全一致的种子数据 → 平台打开即与原型观感一致；
- 删除 backend/data/jdo.db 即可重置回种子状态。
"""
import json
import sqlite3
from datetime import datetime, timedelta

from . import config


def get_conn() -> sqlite3.Connection:
    """获取一个 SQLite 连接（调用方负责 close，推荐 with closing(...)）。"""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------- 建表
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(              -- 成员（登录 + 系统设置页成员表）
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE, password TEXT,         -- 原型阶段明文即可，接 JWT 时换哈希
  name TEXT, role TEXT                         -- 角色：管理员 / 测试工程师 / 只读
);
CREATE TABLE IF NOT EXISTS cases(              -- 功能用例（手工回归 checklist，覆盖率分母）
  id TEXT PRIMARY KEY,                         -- 用例编号即主键，Excel 导入按它 upsert
  app TEXT, module TEXT, priority TEXT,
  title TEXT,                                  -- 用例标题（官方 Excel 导入带来）
  req_id TEXT,                                 -- 需求 ID（如 F03_UC004，官方报告溯源）
  source TEXT,                                 -- seed / official / manual：分母来源
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS scripts(            -- 自动化脚本（覆盖率分子）
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, app TEXT, version TEXT,
  framework TEXT,                              -- 归属框架：jdo_framework / media_automation …
  file_name TEXT, file_path TEXT,              -- 原件存放于 data/uploads/，种子数据无文件
  last_result TEXT DEFAULT 'pending',          -- ok / fail / pending，执行后回写
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS script_case(        -- 脚本↔手工用例 映射（多对多）
  script_id INTEGER, case_id TEXT,
  module TEXT, priority TEXT,                  -- 冗余快照：展开行直接展示，无需回查 cases
  PRIMARY KEY(script_id, case_id)
);
CREATE TABLE IF NOT EXISTS tasks(              -- 测试任务（回归套件 = App范围 × 品牌范围）
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  apps_label TEXT, brands_label TEXT,          -- 列表展示用文案（与原型一致）
  apps_json TEXT, brands_json TEXT,            -- 结构化范围，执行时使用
  scope TEXT, mode TEXT,                       -- 用例范围（全部/仅P0/仅P1）· 执行方式（并行/串行）
  case_count INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS reports(            -- 执行报告（一次执行 × 一个品牌 = 一条）
  id INTEGER PRIMARY KEY AUTOINCREMENT,        -- 种子从 2038 起，与原型编号衔接
  task TEXT, app TEXT, brand TEXT,
  pass INTEGER, total INTEGER, dur TEXT,
  status TEXT,                                 -- 通过 / 失败
  time TEXT,                                   -- 'YYYY-MM-DD HH:MM'
  trigger_type TEXT                            -- 手动 / 定时（trigger 是 SQLite 保留字）
);
CREATE TABLE IF NOT EXISTS report_cases(       -- 报告内每条用例的结果明细
  report_id INTEGER, case_id TEXT, name TEXT,
  result TEXT                                  -- ok / fail
);
CREATE TABLE IF NOT EXISTS devices(            -- 品牌台架
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, brand TEXT, udid TEXT,
  resolution TEXT, os TEXT,
  online INTEGER, agent_ready INTEGER          -- 在线 / 设备代理就绪（0|1）
);
CREATE TABLE IF NOT EXISTS apps(               -- 被测 App 登记（执行时 am start 与账号注入用）
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE, package TEXT, activity TEXT,
  version TEXT, account TEXT
);
CREATE TABLE IF NOT EXISTS schedules(          -- 定时调度计划
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, cron_label TEXT, scope_label TEXT,
  next_time TEXT, enabled INTEGER
);
CREATE TABLE IF NOT EXISTS settings(           -- 键值配置（webhook、通知开关）
  key TEXT PRIMARY KEY, value TEXT
);
CREATE TABLE IF NOT EXISTS coverage_trend(     -- 覆盖率趋势快照（按版本）
  version TEXT PRIMARY KEY, coverage INTEGER
);
"""


# ---------------------------------------------------------------- 种子数据
# 与 doc/原型-交互版.html 内置示例数据保持一致，保证首次打开观感与原型相同。

# 各 App 的手工用例（= 原型 casesByApp，是原型用例页 8 条示例的超集）
SEED_CASES = {
    "酷我音乐": [("KW-PLAY-001", "播放控制", "P0"), ("KW-SRCH-002", "搜索", "P0"),
             ("KW-PLAY-005", "切歌", "P1"), ("KW-VOL-001", "音量调节", "P1"),
             ("KW-PLAY-008", "播放状态校验", "P0"), ("KW-FAV-003", "收藏", "P1")],
    "喜马拉雅": [("XM-PLAY-001", "播放控制", "P0"), ("XM-SRCH-002", "搜索", "P0"),
             ("XM-PLAY-006", "倍速", "P1"), ("XM-SUB-004", "订阅", "P1"),
             ("XM-PLAY-009", "播放状态校验", "P0")],
    "乐听": [("LT-PLAY-003", "播放控制", "P1"), ("LT-SRCH-001", "搜索", "P1")],
    "爱奇艺": [("IQ-PLAY-001", "视频播放", "P0"), ("IQ-PLAY-003", "清晰度切换", "P1"),
            ("IQ-PLAY-007", "播放状态校验", "P0"), ("IQ-SRCH-002", "搜索", "P0")],
    "Launcher": [("LAU-ICON-001", "图标布局", "P0"), ("LAU-ICON-004", "图标点击", "P0")],
    "车内会议": [("MEET-JOIN-001", "入会", "P0"), ("MEET-MIC-002", "麦克风", "P1")],
}

# 脚本及其覆盖的用例（name, app, version, last_result, [case_id,...]）
SEED_SCRIPTS = [
    ("酷我音乐 · 播放回归", "酷我音乐", "v1.3", "ok",
     ["KW-PLAY-001", "KW-SRCH-002", "KW-PLAY-005", "KW-VOL-001", "KW-PLAY-008"]),
    ("喜马拉雅 · 搜索播放", "喜马拉雅", "v1.1", "fail",
     ["XM-PLAY-001", "XM-SRCH-002", "XM-PLAY-006", "XM-PLAY-009"]),
    ("爱奇艺 · 视频播放", "爱奇艺", "v1.0", "ok",
     ["IQ-PLAY-001", "IQ-PLAY-003", "IQ-PLAY-007"]),
    ("Launcher · 图标校验", "Launcher", "v1.2", "ok",
     ["LAU-ICON-001", "LAU-ICON-004"]),
]

SEED_TASKS = [
    ("发版全量回归", "全部 6 App", "奥迪 / 保时捷 / 大众",
     ["酷我音乐", "喜马拉雅", "乐听", "爱奇艺", "Launcher", "车内会议"],
     ["奥迪", "保时捷", "大众"], "全部用例", "多品牌并行", 96),
    ("核心冒烟", "酷我 / 喜马 / 爱奇艺", "奥迪 / 保时捷",
     ["酷我音乐", "喜马拉雅", "爱奇艺"], ["奥迪", "保时捷"], "全部用例", "多品牌并行", 18),
    ("音乐类专项", "酷我 / 喜马 / 乐听", "奥迪",
     ["酷我音乐", "喜马拉雅", "乐听"], ["奥迪"], "全部用例", "串行", 27),
]

SEED_DEVICES = [
    ("奥迪台架 #1", "奥迪", "AUDI-A8-IVI-001", "1920×720", "AAOS 12", 1, 1),
    ("保时捷台架 #2", "保时捷", "PORSCHE-CAYENNE-002", "2560×980", "Android 11", 1, 1),
    ("大众台架 #3", "大众", "VW-ID6-IVI-003", "1440×540", "Android 10", 0, 0),
]

SEED_APPS = [
    ("酷我音乐", "cn.kuwo.kwmusiccar", "MainActivity", "9.2.1", "test_kuwo01"),
    ("喜马拉雅", "com.ximalaya.ting.car", "WelcomeActivity", "8.1.0", "test_xmly"),
    ("乐听", "com.leting.car", "HomeActivity", "3.4.0", "test_lt"),
    ("爱奇艺", "com.qiyi.video.car", "SplashActivity", "11.0.5", "test_iqy"),
    ("Launcher", "com.oem.carlauncher", "Launcher", "—", "—"),
    ("车内会议", "com.oem.meeting", "MeetingMain", "2.1.0", "test_meet"),
]

SEED_USERS = [
    ("admin", "123456", "张三", "管理员"),
    ("lisi", "123456", "李四", "测试工程师"),
    ("wangwu", "123456", "王五", "只读"),
]

SEED_TREND = [("V1.0", 12), ("V1.1", 25), ("V1.2", 38), ("V1.3", 47), ("V1.4", 55), ("V1.5", 62)]

SEED_SETTINGS = [
    ("webhook", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."),
    ("notify_fail", "1"),      # 用例失败时实时推送
    ("notify_daily", "1"),     # 每日回归汇总报告
]


def _seed_reports(conn: sqlite3.Connection, now: datetime):
    """报告种子：时间锚定「今天/昨天」，让工作台『最近执行/今日执行』打开即有数据。

    显式指定 id 2038~2041（衔接原型编号），后续真实执行自增为 2042+。
    """
    today, yesterday = now, now - timedelta(days=1)
    rows = [
        (2041, "核心冒烟", "酷我音乐", "奥迪", 9, 9, "12.4s", "通过",
         today.strftime("%Y-%m-%d") + " 10:24", "手动",
         [("KW-PLAY-001", "播放控制", "ok"), ("KW-SRCH-002", "搜索", "ok"),
          ("KW-PLAY-008", "播放状态校验", "ok")]),
        (2040, "核心冒烟", "喜马拉雅", "保时捷", 8, 9, "15.1s", "失败",
         today.strftime("%Y-%m-%d") + " 09:50", "手动",
         [("XM-PLAY-001", "播放控制", "fail"), ("XM-SRCH-002", "搜索", "ok"),
          ("XM-PLAY-009", "播放状态校验", "ok")]),
        (2039, "夜间全量回归", "多 App", "大众", 92, 96, "21m", "失败",
         today.strftime("%Y-%m-%d") + " 02:00", "定时",
         [("IQ-PLAY-001", "视频播放", "fail"), ("KW-PLAY-001", "播放控制", "ok"),
          ("XM-PLAY-001", "播放控制", "ok")]),
        (2038, "音乐类专项", "酷我音乐", "奥迪", 27, 27, "6m", "通过",
         yesterday.strftime("%Y-%m-%d") + " 18:12", "手动",
         [("KW-PLAY-001", "播放控制", "ok"), ("KW-SRCH-002", "搜索", "ok")]),
    ]
    for rid, task, app, brand, ok, total, dur, st, t, trig, case_rows in rows:
        conn.execute(
            "INSERT INTO reports(id,task,app,brand,pass,total,dur,status,time,trigger_type)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (rid, task, app, brand, ok, total, dur, st, t, trig))
        conn.executemany(
            "INSERT INTO report_cases(report_id,case_id,name,result) VALUES(?,?,?,?)",
            [(rid, cid, nm, res) for cid, nm, res in case_rows])


def _migrate(conn: sqlite3.Connection):
    """给已存在的旧库补新增列（SQLite 无 IF NOT EXISTS，靠 pragma 检测）。

    新列均可空、无默认约束 —— 旧数据读出为 NULL，业务层按 seed/manual 兜底。
    """
    add = {
        "cases": [("title", "TEXT"), ("req_id", "TEXT"), ("source", "TEXT")],
        "scripts": [("framework", "TEXT")],
    }
    for table, cols in add.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, typ in cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def init_db():
    """建库建表；空库时灌入种子数据（幂等：有数据则跳过）。"""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)                          # 旧库补列（新库上面已建全，这里为空操作）
        conn.commit()
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return  # 已初始化过
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M")

        conn.executemany("INSERT INTO users(username,password,name,role) VALUES(?,?,?,?)", SEED_USERS)

        for app, items in SEED_CASES.items():
            conn.executemany(
                "INSERT INTO cases(id,app,module,priority,created_at) VALUES(?,?,?,?,?)",
                [(cid, app, mod, pri, ts) for cid, mod, pri in items])

        # 脚本 + 映射：映射里冗余 module/priority 快照，取自 SEED_CASES。
        # 列表按 id 倒序展示（新上传在前），故种子反向插入以保持原型的显示顺序。
        case_meta = {cid: (mod, pri) for items in SEED_CASES.values() for cid, mod, pri in items}
        for name, app, ver, result, case_ids in reversed(SEED_SCRIPTS):
            cur = conn.execute(
                "INSERT INTO scripts(name,app,version,last_result,created_at) VALUES(?,?,?,?,?)",
                (name, app, ver, result, ts))
            conn.executemany(
                "INSERT INTO script_case(script_id,case_id,module,priority) VALUES(?,?,?,?)",
                [(cur.lastrowid, cid, *case_meta[cid]) for cid in case_ids])

        for name, al, bl, apps, brands, scope, mode, cnt in reversed(SEED_TASKS):
            conn.execute(
                "INSERT INTO tasks(name,apps_label,brands_label,apps_json,brands_json,scope,mode,case_count,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (name, al, bl, json.dumps(apps, ensure_ascii=False),
                 json.dumps(brands, ensure_ascii=False), scope, mode, cnt, ts))

        _seed_reports(conn, now)

        conn.executemany(
            "INSERT INTO devices(name,brand,udid,resolution,os,online,agent_ready) VALUES(?,?,?,?,?,?,?)",
            SEED_DEVICES)
        conn.executemany(
            "INSERT INTO apps(name,package,activity,version,account) VALUES(?,?,?,?,?)", SEED_APPS)

        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d") + " 02:00"
        days_to_sat = (5 - now.weekday()) % 7 or 7          # 下个周六
        sat = (now + timedelta(days=days_to_sat)).strftime("%Y-%m-%d") + " 22:00"
        conn.executemany(
            "INSERT INTO schedules(name,cron_label,scope_label,next_time,enabled) VALUES(?,?,?,?,?)",
            [("夜间全量回归", "每日 02:00", "全部 App · 全部在线品牌", tomorrow, 1),
             ("构建后冒烟", "每次构建触发", "核心 3 App · 奥迪 / 保时捷", "按需", 1),
             ("周末稳定性 Monkey", "每周六 22:00", "酷我 / 喜马 · 奥迪", sat, 0)])

        conn.executemany("INSERT INTO settings(key,value) VALUES(?,?)", SEED_SETTINGS)
        conn.executemany("INSERT INTO coverage_trend(version,coverage) VALUES(?,?)", SEED_TREND)
        conn.commit()
    finally:
        conn.close()
