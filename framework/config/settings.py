"""框架配置：设备地址、被测包名与各模块入口 Activity。

★ 架构关键（P0 真机探明，勿凭直觉改）：
Oneinfo 是「一个 App 包 com.jidouauto.media 内含 4 个媒体模块」
（喜马拉雅 / 酷我 / 爱奇艺 / 乐听），不是 4 个独立 APK；
各模块有独立 Activity，用 am start -n 直接拉起（品牌无关，不点 Launcher）。
"""
import os

# 默认设备：Audi 台架（.32 许可有效；.89 待许可续期）。执行时用环境变量 JDO_DEVICE 覆盖。
# ⚠ 台架重启后需先 adb root（SELinux 包策略拦截 9008 端口，见 doc/上下文.md §0.6）。
DEFAULT_DEVICE = os.environ.get("JDO_DEVICE", "192.168.2.32:5555")

# Oneinfo 媒体聚合包
MEDIA_PKG = "com.jidouauto.media"

# 各模块入口 Activity（酷我为 P0 实测值；其余待抓取后补全）
ACTIVITIES = {
    "kuwo": f"{MEDIA_PKG}/.ui.kuwo.main.KuwoMainActivity",
    # "ximalaya": f"{MEDIA_PKG}/.ui.xmly...",   # TODO: 真机 dumpsys 抓取后补
    # "iqiyi":    f"{MEDIA_PKG}/.ui.iqiyi...",
    # "leting":   f"{MEDIA_PKG}/.ui.leting...",
}

# 显式等待默认超时（秒）
WAIT_TIMEOUT = 10
