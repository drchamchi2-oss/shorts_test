from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main_gpt


def test_media_provider_for_url_classifies_known_sources():
    assert main_gpt.media_provider_for_url("https://upload.wikimedia.org/example.jpg") == "wikimedia"
    assert main_gpt.media_provider_for_url("https://images.pexels.com/photos/1/example.jpg") == "pexels"
    assert main_gpt.media_provider_for_url("https://cdn.pixabay.com/photo/example.jpg") == "pixabay"
    assert main_gpt.media_provider_for_url(None) == "placeholder"


def test_attribution_entries_from_script_uses_image_indices_and_map_first_scene():
    scenes = [
        {"idx": 1, "image_idx": 2, "image_keywords_en": "map query"},
        {"idx": 2, "image_idx": 2, "image_keywords_en": "detail query"},
        {"idx": 3, "image_idx": 99, "image_keywords_en": "missing query"},
    ]
    candidates = [
        "https://upload.wikimedia.org/map.jpg",
        "https://upload.wikimedia.org/detail.jpg",
    ]

    entries = main_gpt.attribution_entries_from_script(
        scenes,
        candidates,
        map_url=candidates[0],
        title_en="Fallback title",
    )

    assert entries[0]["selection"] == "map_first_scene"
    assert entries[0]["image_url"] == candidates[0]
    assert entries[1]["selection"] == "script_image_idx"
    assert entries[1]["image_url"] == candidates[1]
    assert entries[2]["provider"] == "placeholder"
    assert entries[2]["license_review_required"] is True


def test_write_media_attribution_records_dry_run_flag(tmp_path):
    path = tmp_path / "media_attribution.json"
    entry = main_gpt.media_attribution_entry(
        scene_idx=1,
        image_file="images/01.jpg",
        image_url="https://upload.wikimedia.org/example.jpg",
        selection="script_image_idx",
        query="example",
    )

    main_gpt.write_media_attribution(path, [entry], dry_run=True)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["images"][0]["provider"] == "wikimedia"


def test_parser_accepts_dry_run_flag():
    args = main_gpt.build_parser().parse_args(["run", "--dry_run"])

    assert args.dry_run is True
