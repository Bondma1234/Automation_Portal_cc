"""设备连接层（平台组维护）。

规则：脚本/页面对象一律通过 conftest 注入的设备句柄操作，
不要自己 u2.connect —— driver 收口在这里，后续可整体替换。
网络 ADB 设备掉线时自动 adb connect 重连一次。
"""
import subprocess

import uiautomator2 as u2

from config import settings


def _adb_connect(addr: str):
    """网络设备（ip:port）先 adb connect + adb root，容忍失败（可能已连接/已 root）。

    root 是必须的：车机固件用 SELinux 包策略拦截 9008 等自动化端口，
    非 root 时 uiautomator2 服务连不上（详见 doc/上下文.md §0.6）。
    """
    try:
        subprocess.run(["adb", "connect", addr], capture_output=True, timeout=10)
        subprocess.run(["adb", "-s", addr, "root"], capture_output=True, timeout=10)
        subprocess.run(["adb", "connect", addr], capture_output=True, timeout=10)
        # 清掉残留 u2 服务（异常退出会留死锁进程霸占 9008），u2.connect 会重新拉起
        subprocess.run(["adb", "-s", addr, "shell", "pkill", "-9", "-f", "com.wetest.uia2.Main"],
                       capture_output=True, timeout=10)
    except Exception:
        pass


def get_device(addr: str = None):
    """获取 uiautomator2 设备句柄；addr 缺省用 JDO_DEVICE / 配置默认值。"""
    addr = addr or settings.DEFAULT_DEVICE
    if ":" in addr:                 # 网络 ADB（台架常态）先确保已连接
        _adb_connect(addr)
    d = u2.connect(addr)
    d.implicitly_wait(settings.WAIT_TIMEOUT)
    return d
