"""酷我模块基类：归位约定 + 真机探明的选择器常量。

选择器（2026-07-06 于 Audi 台架 .32 复验）：
- 播放条 id_op_prev / id_op_playpause / id_op_next，曲名 tv_title，
  迷你播放条 fragment_mini_player / mini_player；
- 主页工具栏搜索入口：ImageButton，content-desc 为非标值「###搜索」→ descriptionContains；
- 主页默认可能落在「My」卡片页（无歌曲列表），播放入口统一走搜索（见 KuwoPlayerPage.ensure_playing）；
- 界面语言随账号可能是中/英文，选择器一律用 resource-id / content-desc，禁止依赖界面文本。
"""
from config import settings
from core import adb_helper
from core.base_page import BasePage

RID = f"{settings.MEDIA_PKG}:id/"    # resource-id 前缀


class KuwoBase(BasePage):
    """酷我各页面对象的公共基类。"""

    def launch(self):
        """am start 直接拉起酷我模块（跨品牌不点 Launcher）。"""
        adb_helper.am_start(self.d.serial, settings.ACTIVITIES["kuwo"])

    def at_home(self) -> bool:
        """主页标志 = 工具栏搜索按钮存在 且 不在搜索输入页。

        注意不能用 recyclerView 当主页标志：搜索结果页也有 recyclerView。
        """
        return (self.exists(descriptionContains="搜索")
                and not self.exists(resourceId=RID + "editText"))

    def ensure_home(self, max_back: int = 4):
        """归位：回到酷我主页（规则③——每条用例开头必须先归位，不依赖上一条状态）。"""
        self.launch()
        for _ in range(max_back):
            if self.at_home():
                return
            self.d.press("back")
        self.launch()
        self.wait(descriptionContains="搜索")
