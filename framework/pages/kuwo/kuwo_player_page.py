"""酷我播放器页面对象：迷你播放条的播放/暂停/切歌与曲名读取。

播放条 id（2026-07-06 .32 复验，与 P0 记录一致）：
id_op_prev / id_op_playpause / id_op_next / tv_title / fragment_mini_player。
"""
import time

from pages.kuwo.base import KuwoBase, RID


class KuwoPlayerPage(KuwoBase):

    def play_pause(self):
        """点播放/暂停键（迷你播放条）。"""
        self.click(resourceId=RID + "id_op_playpause")
        time.sleep(2)                    # 等媒体会话状态刷新

    def next_track(self):
        self.click(resourceId=RID + "id_op_next")
        time.sleep(2)

    def prev_track(self):
        self.click(resourceId=RID + "id_op_prev")
        time.sleep(2)

    def current_title(self) -> str:
        """迷你播放条当前曲名。"""
        return self.text_of(resourceId=RID + "tv_title")

    def ensure_playing(self, keyword: str = "周杰伦"):
        """确保当前有真实播放（media_session=PLAYING）。

        主页默认标签可能是「My」卡片页（无歌曲列表），所以统一走
        搜索 → 播放第一条 的确定性路径，而不依赖主页列表。
        """
        if self.media_state()["state"] == "PLAYING":
            return
        from pages.kuwo.kuwo_search_page import KuwoSearchPage
        search = KuwoSearchPage(self.d)
        search.open()
        search.search(keyword)
        search.play_first_result()
