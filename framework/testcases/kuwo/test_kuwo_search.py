"""酷我音乐 · 搜索 → 播放 校验（KW-SRCH-002，2026-07-06 真机复验版）。"""
import pytest

from pages.kuwo.kuwo_search_page import KuwoSearchPage


@pytest.mark.case("KW-SRCH-002")
def test_kuwo_search_play(kuwo):
    """搜索关键词 → 播放第一条结果 → media_session 校验真实播放。"""
    page = KuwoSearchPage(kuwo)
    page.open()                              # 内部先 ensure_home 归位（规则③）

    page.search("周杰伦")
    page.play_first_result()

    st = page.media_state()
    assert st["state"] == "PLAYING", f"搜索结果播放未生效：media_session 状态为 {st['state']}"
    assert st["title"], "media_session 未读到曲目 metadata"
