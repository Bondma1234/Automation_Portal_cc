"""酷我音乐 · 播放/暂停 状态校验（KW-PLAY-008，2026-07-06 真机复验版）。

新模块（喜马拉雅/爱奇艺/乐听）照此结构复制扩展：
1) pages/<模块>/ 建页面对象；2) testcases/<模块>/ 写用例并标 @pytest.mark.case。
本地自测：cd framework && python -m pytest testcases/kuwo -v   （设备：环境变量 JDO_DEVICE）
"""
import pytest

from pages.kuwo.kuwo_player_page import KuwoPlayerPage


@pytest.mark.case("KW-PLAY-008")
def test_kuwo_play_pause(kuwo):
    """播放后用 media_session 校验真实播放状态（不能只看 UI，规范要求）。"""
    page = KuwoPlayerPage(kuwo)
    page.ensure_home()                       # 规则③：先归位，不依赖上一条用例的状态

    page.ensure_playing()                    # 无播放则走搜索→播放第一条（确定性入口）
    st = page.media_state()
    assert st["state"] == "PLAYING", f"播放未生效：media_session 状态为 {st['state']}"
    assert st["title"], "media_session 未读到曲目 metadata"

    page.play_pause()                        # 暂停
    st = page.media_state()
    assert st["state"] == "PAUSED", f"暂停未生效：media_session 状态为 {st['state']}"
