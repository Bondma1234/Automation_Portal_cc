"""ADB 系统级操作（平台组维护）：拉起模块 / 媒体状态校验 / logcat。

分工约定：uiautomator2 只管元素交互；am start、dumpsys media_session、
logcat、录屏等系统级操作都收口到本文件（adb shell）。
"""
import re
import subprocess

from config import settings


def _shell(serial: str, cmd: str) -> str:
    """adb -s <serial> shell <cmd>，返回 stdout 文本。"""
    out = subprocess.run(["adb", "-s", serial, "shell", cmd],
                         capture_output=True, timeout=30)
    return out.stdout.decode("utf-8", errors="replace")


def am_start(serial: str, activity: str):
    """按 包名/Activity 直接拉起模块（跨品牌关键：不点 Launcher 图标）。"""
    _shell(serial, f"am start -n {activity}")


def get_media_state(serial: str, pkg: str = settings.MEDIA_PKG) -> dict:
    """读取真实播放状态（音频类用例的核心校验，不能只看 UI）。

    dumpsys media_session 输出结构（2026-07-06 Audi 台架实测）：
        package=com.jidouauto.media                  ← 会话分节
        state=PlaybackState {state=PLAYING(3), ...}  ← 状态为「文字(数字)」格式
        metadata: size=44, description=曲名, 歌手, 专辑
    同一包会有多个「空壳」会话（state=NONE / metadata null），
    取「PLAYING/PAUSED 且带 metadata」的那个。
    返回 {"state": "PLAYING"/"PAUSED"/"UNKNOWN", "title": 曲目或空串}。
    """
    raw = _shell(serial, "dumpsys media_session")
    best = {"state": "UNKNOWN", "title": ""}
    current_pkg, state = None, None
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"package=(\S+)", line)
        if m:                                   # 进入新会话分节
            current_pkg, state = m.group(1), None
            continue
        if current_pkg != pkg:
            continue
        m = re.search(r"state=PlaybackState \{state=([A-Z_]+)\(\d+\)", line)
        if m:
            state = m.group(1)                  # PLAYING / PAUSED / NONE / ...
            continue
        m = re.match(r"metadata: size=(\d+), description=(.+)", line)
        if m and state in ("PLAYING", "PAUSED"):
            title = m.group(2).split(",")[0].strip()
            if int(m.group(1)) > 0 and title and title != "null":
                return {"state": state, "title": title}   # 真实播放会话
            if best["state"] == "UNKNOWN":
                best = {"state": state, "title": ""}      # 有状态无曲目，先记候补
    return best


def logcat_dump(serial: str, lines: int = 400) -> str:
    """抓最近 N 行 logcat（失败现场三件套之一）。"""
    return _shell(serial, f"logcat -d -t {lines}")
