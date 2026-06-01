from __future__ import annotations

import re
from typing import List


def fmt_ass_time(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(s: str) -> str:
    s = (s or "").replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    return s


def allocate_chunk_times(scene_dur: float, chunks: List[str], min_chunk: float = 0.45) -> List[float]:
    if not chunks:
        return []
    max_chunks = max(1, int(scene_dur / min_chunk))
    if len(chunks) > max_chunks:
        merged = []
        buf = ""
        for chunk in chunks:
            if not buf:
                buf = chunk
            elif len(merged) + 1 < max_chunks:
                merged.append(buf)
                buf = chunk
            else:
                buf = (buf + " " + chunk).strip()
        if buf:
            merged.append(buf)
        chunks = merged
    weights = [max(1, len(re.sub(r"\s+", "", chunk))) for chunk in chunks]
    total = float(sum(weights))
    times = [scene_dur * (weight / total) for weight in weights]
    times = [max(min_chunk, t) for t in times]
    total_time = sum(times)
    if total_time > 0:
        scale = scene_dur / total_time
        times = [t * scale for t in times]
    diff = scene_dur - sum(times)
    times[-1] += diff
    return times
