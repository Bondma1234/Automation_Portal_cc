"""Page Object 基类（平台组维护）。

定位约定（P0 真机验证）：
- 优先级 resourceId > text > descriptionContains，禁止写死坐标；
- 本 App 的 content-desc 是非标值（如「###搜索」），匹配用 descriptionContains。
"""
from config import settings
from core import adb_helper


class BasePage:
    """所有页面对象继承本类；封装显式等待与常用动作，用例层不碰裸选择器。"""

    def __init__(self, d):
        self.d = d                      # uiautomator2 设备句柄（conftest 注入）

    # ---------- 基础动作 ----------
    def wait(self, timeout: float = settings.WAIT_TIMEOUT, **selector):
        """显式等待元素出现并返回；超时抛断言错误（带中文信息便于定位）。"""
        el = self.d(**selector)
        assert el.wait(timeout=timeout), f"元素未出现：{selector}"
        return el

    def click(self, **selector):
        self.wait(**selector).click()

    def text_of(self, **selector) -> str:
        return self.wait(**selector).get_text() or ""

    def exists(self, **selector) -> bool:
        return self.d(**selector).exists

    # ---------- 媒体校验 ----------
    def media_state(self) -> dict:
        """真实播放状态（底层 dumpsys media_session），音/视频用例必用。"""
        return adb_helper.get_media_state(self.d.serial)
