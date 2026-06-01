import shorts_media
import shorts_rendering


def test_media_helpers_live_in_focused_module():
    assert shorts_media.cache_key_for_url("https://example.com/image.jpg") == "e5db82b5bf63d49d"
    assert shorts_media.media_provider_for_url("https://upload.wikimedia.org/example.jpg") == "wikimedia"


def test_rendering_helpers_live_in_focused_module():
    assert shorts_rendering.fmt_ass_time(1.25) == "0:00:01.25"
    assert shorts_rendering.ass_escape("{caption}") == r"\{caption\}"
    assert shorts_rendering.allocate_chunk_times(0.2, ["a", "b"]) == [0.2]
