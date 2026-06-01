from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote, urlparse


def normalize_wikimedia_url(url: str, width: int = 1080) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""
        if "wikimedia.org" not in host:
            return url
        filename = None
        if "/wikipedia/commons/thumb/" in path:
            parts = path.split("/")
            thumb_index = None
            for i, part in enumerate(parts):
                if part == "thumb":
                    thumb_index = i
                    break
            if thumb_index is not None and len(parts) > thumb_index + 3:
                filename = parts[thumb_index + 3]
        if not filename and "/wikipedia/commons/" in path:
            filename = path.split("/")[-1]
        if not filename:
            return url
        filename = unquote(filename)
        filename = filename.split("?")[0].split("#")[0].strip()
        if not filename:
            return url
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width={int(width)}"
    except Exception:
        return url


def cache_key_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def media_provider_for_url(url: Optional[str]) -> str:
    if not url:
        return "placeholder"
    host = (urlparse(url).netloc or "").lower()
    if "wikimedia.org" in host or "wikipedia.org" in host:
        return "wikimedia"
    if "pexels.com" in host or "pexels" in host:
        return "pexels"
    if "pixabay.com" in host or "pixabay" in host:
        return "pixabay"
    return "unknown"


def media_attribution_entry(
    scene_idx: int,
    image_file: str,
    image_url: Optional[str],
    selection: str,
    query: str,
) -> Dict[str, Any]:
    return {
        "scene_idx": int(scene_idx),
        "image_file": image_file,
        "image_url": image_url,
        "provider": media_provider_for_url(image_url),
        "selection": selection,
        "query": query,
        "license_review_required": True,
    }


def write_media_attribution(path: Path, entries: List[Dict[str, Any]], dry_run: bool = False) -> None:
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dry_run": bool(dry_run),
        "review_note": "Review provider terms and source licenses before publishing generated media.",
        "images": entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def attribution_entries_from_script(
    scenes: List[Dict],
    cand_urls: List[str],
    map_url: Optional[str],
    title_en: str,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for i, scene in enumerate(scenes, start=1):
        idx = int(scene.get("idx", i))
        keywords = (scene.get("image_keywords_en") or "").strip()
        query = keywords or title_en
        image_idx = 0
        try:
            image_idx = int(scene.get("image_idx") or 0)
        except Exception:
            image_idx = 0
        img_url: Optional[str] = None
        selection = "placeholder"
        if 1 <= image_idx <= len(cand_urls):
            img_url = cand_urls[image_idx - 1]
            selection = "script_image_idx"
        if map_url and idx == 1 and cand_urls:
            img_url = cand_urls[0]
            selection = "map_first_scene"
        entries.append(media_attribution_entry(idx, f"images/{idx:02d}.jpg", img_url, selection, query))
    return entries
