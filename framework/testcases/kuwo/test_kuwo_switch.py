"""酷我音乐 · 切歌 校验（KW-PLAY-005，2026-07-06 真机复验版）。"""
import pytest

from pages.kuwo.kuwo_player_page import KuwoPlayerPage


@pytest.mark.case("KW-PLAY-005")
def test_kuwo_switch_next(kuwo):
    """播放 → 切下一首 → media_session 曲目变化且仍在播放。"""
    page = KuwoPlayerPage(kuwo)
    page.ensure_home()                       # 规则③：先归位

    page.ensure_playing()
    before = page.media_state()
    assert before["state"] == "PLAYING", f"前置播放未生效：{before['state']}"
    assert before["title"], "前置播放未读到曲目 metadata"

    page.next_track()
    after = page.media_state()
    assert after["state"] == "PLAYING", f"切歌后未在播放：{after['state']}"
    assert after["title"] and after["title"] != before["title"], \
        f"切歌后曲目未变化：{before['title']} -> {after['title']}"
