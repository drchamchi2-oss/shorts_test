from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main_gpt


def test_shorten_title_to_fit_limits_and_cleans():
    assert main_gpt.shorten_title_to_fit('"ABCDEFGHIJKLMNO"', max_chars=5) == "ABCDE"


def test_sanitize_title_for_path_keeps_stable_filename_shape():
    assert main_gpt.sanitize_title_for_path("A/B: C?") == "A_B_C"
    assert main_gpt.sanitize_title_for_path("x" * 100) == "x" * 80


def test_safe_json_loads_accepts_fenced_json_with_trailing_comma():
    assert main_gpt.safe_json_loads('```json\n{"value": 1,}\n```') == {"value": 1}


def test_cache_key_for_url_is_sha256_prefix():
    key = main_gpt.cache_key_for_url("https://example.com/image.jpg")

    assert key == "e5db82b5bf63d49d"
    assert len(key) == 16


def test_caption_chunks_are_trimmed_and_non_empty():
    chunks = main_gpt.split_korean_caption_chunks(
        "This is a first caption sentence. This is a second caption sentence.",
        max_len=20,
    )

    assert chunks
    assert all(chunk == chunk.strip() for chunk in chunks)
    assert all(chunk for chunk in chunks)
