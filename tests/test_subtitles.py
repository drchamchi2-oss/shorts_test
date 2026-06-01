from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main_gpt


def _ass_seconds(value: str) -> float:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})\.(\d{2})", value)
    assert match is not None
    hours, minutes, seconds, centiseconds = [int(part) for part in match.groups()]
    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100


def _dialogue_times(ass_text: str):
    for line in ass_text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        yield _ass_seconds(fields[1]), _ass_seconds(fields[2])


def test_allocate_chunk_times_merges_chunks_for_short_scenes():
    chunks = ["first", "second", "third"]

    times = main_gpt.allocate_chunk_times(0.2, chunks, min_chunk=0.45)

    assert len(times) == 1
    assert times[0] == 0.2


def test_write_ass_subtitles_keeps_dialogue_times_monotonic(tmp_path):
    ass_path = tmp_path / "subs.ass"
    scenes = [
        {"narration": "First sentence. Second sentence. Third sentence."},
        {"narration": "Short closing line."},
    ]

    main_gpt.write_ass_subtitles_sentence_style(ass_path, scenes, [0.35, 1.25])

    spans = list(_dialogue_times(ass_path.read_text(encoding="utf-8")))
    assert spans
    assert all(start < end for start, end in spans)
    assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1))
    assert spans[-1][1] <= 1.60


def test_write_ass_subtitles_skips_empty_narration(tmp_path):
    ass_path = tmp_path / "subs.ass"

    main_gpt.write_ass_subtitles_sentence_style(ass_path, [{"narration": "   "}], [0.5])

    assert "Dialogue:" not in ass_path.read_text(encoding="utf-8")
