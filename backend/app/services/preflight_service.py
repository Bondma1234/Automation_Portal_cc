"""真机执行前的环境预检（借鉴 Codex 平台设计，按我方排障经验调整预算）。

目的：把「台架环境坏」和「测试失败」分开 —— 环境不行就整列记「未执行」并说清原因，
不让环境问题伪装成大片红（2026-07-13 上午的教训）。

与 Codex 版的关键差异：**前台等待预算 90s**（它给 30s）——台架劣化时酷我冷启动
实测 45s+（am start -W TotalTime: 45425），App 能起但慢不该被判死；已在前台则秒过
（顺带完成热身，首个用例更稳）。

检查项：
1. adb 可达（必需）；
2. locale / App 版本（只采集进日志，不阻塞——语言坑由框架选择器规范治理）；
3. 被测 App 到前台（必需，预算 90s 轮询；不在前台先 am start -W 拉起）；
4. UI 状态扫描（必需）：许可证过期提示 → 阻塞；卡「正在加载」→ 等 8s 复查一次，
   仍卡 → 阻塞（这就是 07-13 的坏状态现场）。
"""
import re
import subprocess
import time

from .. import config


def _adb(serial: str, *args: str, timeout: int = 20):
    """adb 命令：返回 (rc, 合并输出文本)；异常吞成 rc=-1（预检不抛，只判定）。"""
    try:
        p = subprocess.run(["adb", "-s", serial, *args], capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", errors="replace").strip()
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def _foreground_ok(serial: str, package: str) -> bool:
    """被测包是否在前台（看窗口焦点，比 dump XML 轻量得多）。

    ⚠ 管道命令必须整体作为**一个** shell 参数：adb 多参数拼接会丢引号分组，
    设备上会变成跑全量 dumpsys（超时）—— 2026-07-14 踩坑记录。
    """
    _, out = _adb(serial, "shell",
                  "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'", timeout=12)
    return package in out


def _ui_dump(serial: str) -> str:
    """抓一次 UI 层级文本（供许可证/坏状态扫描）；失败返回空串不阻塞。"""
    remote = "/sdcard/jdo_preflight.xml"
    rc, _ = _adb(serial, "shell", "uiautomator", "dump", remote, timeout=25)
    if rc != 0:
        return ""
    _, xml = _adb(serial, "shell", "cat", remote, timeout=15)
    _adb(serial, "shell", "rm", "-f", remote, timeout=10)
    return xml


def run_preflight(serial: str, label: str, add_log, should_stop=None) -> bool:
    """跑完整预检，日志逐项回写执行中心；返回是否放行该列。

    should_stop: 可选回调（job 终止标志），长等待期间感知取消。
    """
    app = config.PREFLIGHT_APP
    pkg = app["package"]
    add_log(f"› {label} 环境预检开始…")

    # 1) adb 可达
    _, state = _adb(serial, "get-state", timeout=10)
    if state.strip() != "device":
        add_log(f"⚠ {label} 预检未通过：adb 不可达（{state or '无响应'}）")
        return False

    # 2) 采集告警（非阻塞）：locale / 被测 App 版本（管道整体单参数，见 _foreground_ok 注释）
    _, loc = _adb(serial, "shell", "getprop", "persist.sys.locale", timeout=10)
    _, vd = _adb(serial, "shell", f"dumpsys package {pkg} | grep versionName", timeout=20)
    m = re.search(r"versionName=(\S+)", vd)
    ver = m.group(1) if m else "unknown"

    # 3) 被测 App 主界面到前台（预算内轮询）。
    # 焦点匹配用 Activity 类名而非包名：卡在 FullBlockingActivity 等阻塞页时
    # 包名也在前台，会误判通过（2026-07-14 现场）。等不到时 force-stop 冷启动自愈一次。
    marker = app["component"].rsplit(".", 1)[-1]     # KuwoMainActivity

    def _wait_foreground(budget: int):
        deadline = time.time() + budget
        while time.time() < deadline:
            if should_stop and should_stop():
                return None                          # 收到终止请求
            if _foreground_ok(serial, marker):
                return True
            time.sleep(3)
        return False

    launched = False
    ok = _foreground_ok(serial, marker)
    if not ok:
        add_log(f"› {label} 拉起被测 App 主界面…")
        _adb(serial, "shell", "am", "start", "-W", "-a", app["action"], "-n", app["component"],
             timeout=config.PREFLIGHT_FOREGROUND_TIMEOUT)
        launched = True
        ok = _wait_foreground(60)
    if ok is False:                                  # 自愈：坏状态（卡阻塞页/加载页）冷启动可清
        add_log(f"› {label} 主界面未就绪，force-stop 冷启动自愈重试"
                f"（预算 {config.PREFLIGHT_FOREGROUND_TIMEOUT}s）…")
        _adb(serial, "shell", "am", "force-stop", pkg, timeout=15)
        time.sleep(2)
        _adb(serial, "shell", "am", "start", "-W", "-a", app["action"], "-n", app["component"],
             timeout=config.PREFLIGHT_FOREGROUND_TIMEOUT)
        launched = True
        ok = _wait_foreground(config.PREFLIGHT_FOREGROUND_TIMEOUT)
    if ok is None:
        add_log(f"⚠ {label} 预检期间收到终止请求")
        return False
    if not ok:
        add_log(f"⚠ {label} 预检未通过：{marker} 未到前台（含 force-stop 自愈重试）——"
                "台架状态劣化，先手动确认酷我能打开，必要时重启台架")
        return False

    # 4) UI 状态扫描：许可证过期 / 卡「正在加载」坏状态（07-13 现场）
    xml = _ui_dump(serial)
    if xml and re.search(r"许可证.{0,8}过期|授权.{0,8}过期|license\s*expired|licen[cs]e\s*invalid",
                         xml, re.I):
        add_log(f"⚠ {label} 预检未通过：界面出现许可证过期提示，请先续期")
        return False
    if xml and "正在加载" in xml:
        add_log(f"› {label} 首页仍在加载，8s 后复查…")
        time.sleep(8)
        xml = _ui_dump(serial)
        if xml and "正在加载" in xml:
            add_log(f"⚠ {label} 预检未通过：酷我卡「正在加载」坏状态（force-stop 冷启动可自愈，"
                    "或重启台架）")
            return False

    add_log(f"✓ {label} 预检通过 · locale={loc or '?'} · App {ver} · "
            + ("冷启动完成（已热身）" if launched else "App 已在前台"))
    return True
