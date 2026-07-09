"""酷我搜索页面对象（2026-07-06 Audi 台架 .32 真机复验）。

- 主页搜索入口：content-desc「###搜索」→ descriptionContains；
- 输入框：resource-id editText（回车提交）；
- 结果列表：recyclerView（desc=###searchlist），结果项标题 id = audio_name
  （注意与 P0 记录的列表项 id「title」不同，本页以 audio_name 为准）。
"""
import time

from pages.kuwo.base import KuwoBase, RID


class KuwoSearchPage(KuwoBase):

    def open(self):
        """从主页进入搜索页（规则③：先归位再进入）。"""
        self.ensure_home()
        self.click(descriptionContains="搜索")

    def search(self, keyword: str):
        """输入关键词并发起搜索。"""
        box = self.wait(resourceId=RID + "editText")
        box.click()
        box.set_text(keyword)
        self.d.press("enter")            # 车机键盘无独立搜索按钮时用回车提交

    def play_first_result(self):
        """点搜索结果第一条开始播放（结果项标题 id = audio_name）。"""
        self.wait(resourceId=RID + "audio_name")
        self.d(resourceId=RID + "audio_name")[0].click()
        time.sleep(2)                    # 等媒体会话状态刷新
