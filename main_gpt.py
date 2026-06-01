# -*- coding: utf-8 -*-
"""
OPARTS / 고대유적 / 고대문명 Shorts Factory (단일 파일)

이 스크립트는 위키백과 기반 유튜브 숏츠를 생성합니다.
요청사항 반영:
- 구글/네이버 트렌드 기반 질문 풀 갱신
- 강건한 씬 추출 및 대체 대본 생성
- 워터마크 적용, 경고/에러 중심 로그, 산출물 정리 개선
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import time
import hashlib
from urllib.parse import urlparse, unquote, quote
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

from openai import OpenAI

# =========================
# 기본 설정
# =========================
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "out_araboza"
ASSETS_DIR = BASE_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
BGM_DIR = BASE_DIR / "bgm_no_attrib"
BGM_FIXED = BGM_DIR / "mystery.mp3"

W, H = 1080, 1920
FPS = 30

SAFE_X = 70
TITLE_BOX_H = 280
TOP_BAR_ALPHA = 0.92
TITLE_COLOR = (255, 215, 0)
TITLE_STROKE = (0, 0, 0)
TITLE_STROKE_W = 8
BOTTOM_BAR_H = 400
BOTTOM_BAR_ALPHA = 0.92

ASS_SUB_COLOR = "&H00FFFFFF"
ASS_OUTLINE_COLOR = "&H00000000"
ASS_FONT_SIZE = 70

MIN_SCENES = 10
MAX_SCENES = 15

TOPIC_KEYWORDS = [
    "oopart", "ooparts",
    "ancient", "ruins", "civilization", "civilisation",
    "artifact", "ancient technology",
    "megalith", "megalithic",
    "lost city", "lost civilization",
    "pyramid", "stone circle", "dolmen",
    "antikythera", "baghdad battery", "pumapunku", "baalbek",
    "nan madol", "gobekli tepe", "nazca", "moai",
    "archaeological site", "archaeology",
    "inscription", "tablet", "relic", "mummy", "tomb",
]

TITLE_BLACKLIST = {
    "Stonehenge",
    "Great Pyramid of Giza",
    "Pyramids",
    "Pyramid",
    "Ancient Egypt",
    "Machu Picchu",
    "Atlantis",
}

WIKI_API = "https://en.wikipedia.org/w/api.php"

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "verse"
TTS_LEADIN_S = 0.35
VOICE_SPEED = 1.5
TARGET_MIN = 58.0
TARGET_MAX = 62.0
TARGET_SEC = 60.0
END_PAD_S = 1.4
BGM_FADE_S = 1.2
AUDIO_XFADE_S = 0.08
PEXELS_URL = "https://api.pexels.com/v1/search"
PIXABAY_URL = "https://pixabay.com/api/"
WIKI_API_COMMONS = "https://commons.wikimedia.org/w/api.php"

FEEDBACK_JSON = BASE_DIR / "oparts_feedback.json"

FALLBACK_QUESTIONS: List[Dict[str, str]] = [
    {"ko": "고대 지도 논쟁", "en": "ancient map controversy"},
    {"ko": "수수께끼 유적", "en": "mysterious archaeological site"},
    {"ko": "고대 배터리", "en": "baghdad battery"},
]

VERBOSE = False


# =========================
# 로그
# =========================
def now_kst() -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO") -> None:
    if level.upper() in {"WARN", "WARNING", "ERROR"}:
        print(f"[{now_kst()}] {level.upper()}: {msg}", flush=True)
    elif VERBOSE:
        print(f"[{now_kst()}] INFO: {msg}", flush=True)


def vlog(msg: str) -> None:
    if VERBOSE:
        print(f"[{now_kst()}] DEBUG: {msg}", flush=True)


# =========================
# 파일/경로 유틸
# =========================
def shorten_title_to_fit(title: str, max_chars: int = 15) -> str:
    if not title:
        return ""
    t = re.sub(r"[\r\n]+", " ", title).strip()
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[\"'“”‘’\[\]\(\)<>]+", "", t).strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars].rstrip()
    cut = re.sub(r"(그리고|하지만|그래서|또는|즉|다만)$", "", cut).strip()
    return cut


def refine_title_ko(client: OpenAI, raw_title: str, max_chars: int = 15) -> str:
    raw = (raw_title or "").strip()
    if not raw:
        return ""
    prompt = f"""아래 제목을 유튜브 숏츠용으로 더 몰입감 있게 다듬어주세요.

조건:
- 한국어, 띄어쓰기 자연스럽게.
- {max_chars}자 이내(공백 포함).
- 과장/선동/비하/선정적 표현 금지. 대신 긴장감/호기심 유발 단어는 적극 사용.
- 이모지/해시태그/따옴표/괄호 금지.
- 결과는 제목 한 줄만.

원본 제목: {raw}
"""
    try:
        r = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )
        t = (getattr(r, "output_text", "") or "").strip()
    except Exception:
        t = raw
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[\"'“”‘’\[\]\(\)<>]+", "", t).strip()
    return shorten_title_to_fit(t, max_chars=max_chars)


def sanitize_title_for_path(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:80] if len(s) > 80 else s


def make_out_dir(base_out: Path, title_en: str) -> Path:
    today = dt.date.today().strftime("%Y-%m-%d")
    tstamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = sanitize_title_for_path(title_en or "untitled")
    out = base_out / today / f"{tstamp}_{safe_title}"
    out.mkdir(parents=True, exist_ok=True)
    return out


# =========================
# Feedback
# =========================
@dataclass
class ScoreParams:
    cutline: float = 8.0
    golden: float = 15.0


def load_feedback() -> ScoreParams:
    if FEEDBACK_JSON.exists():
        try:
            d = json.loads(FEEDBACK_JSON.read_text(encoding="utf-8"))
            return ScoreParams(float(d.get("cutline", 8.0)), float(d.get("golden", 15.0)))
        except Exception:
            return ScoreParams()
    return ScoreParams()


def save_feedback(sp: ScoreParams) -> None:
    FEEDBACK_JSON.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_JSON.write_text(json.dumps({"cutline": sp.cutline, "golden": sp.golden}, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_time_feedback(sp: ScoreParams, seconds_to_lock: float) -> ScoreParams:
    if seconds_to_lock <= 30:
        sp.cutline = min(12.0, sp.cutline + 0.5)
        sp.golden = min(22.0, sp.golden + 1.0)
    elif seconds_to_lock > 60:
        sp.cutline = max(4.0, sp.cutline - 0.5)
        sp.golden = max(8.0, sp.golden - 1.0)
    return sp



# =========================
# Wikipedia helpers
# =========================
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "OPARTSShortsFactory/1.6 (Windows; local script)",
        "Accept": "application/json,text/plain,*/*",
    })
    return s


def http_get_json(sess: requests.Session, url: str, params: dict, timeout: int = 25, retries: int = 4) -> dict:
    last_err = None
    for i in range(retries):
        try:
            r = sess.get(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(0.7 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(0.5 * (i + 1))
    raise last_err


def wiki_search_titles(sess: requests.Session, query: str, limit: int = 25) -> List[str]:
    js = http_get_json(sess, WIKI_API, {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    })
    return [it["title"] for it in js.get("query", {}).get("search", [])]


def wiki_extract(sess: requests.Session, title: str, intro_only: bool) -> str:
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "titles": title,
        "format": "json",
    }
    if intro_only:
        params["exintro"] = 1
    js = http_get_json(sess, WIKI_API, params, timeout=30)
    pages = js.get("query", {}).get("pages", {})
    for _, page in pages.items():
        return page.get("extract", "") or ""
    return ""


def is_candidate_title(title: str) -> bool:
    if not title or title in TITLE_BLACKLIST:
        return False
    if title.lower().startswith("list of "):
        return False
    if re.search(r"\b(century|millennium|timeline|history of)\b", title.lower()):
        return False
    return True


def is_oparts_like(title: str, text: str) -> bool:
    hay = (title + "\n" + text).lower()
    hits = sum(1 for kw in TOPIC_KEYWORDS if kw in hay)
    return (hits >= 2) and (len(text.strip()) >= 5000)


def pick_topic(sess: requests.Session, verbose: bool, max_tries: int = 120) -> Tuple[str, str]:
    seed_queries = [
        "controversial archaeological discovery",
        "ancient artifact disputed origin",
        "mysterious inscription discovered",
        "ancient map controversy",
        "out of place artifact hoax debate",
        "ancient technology claim archaeology",
        "megalithic site unexplained debate",
        "ancient tomb unusual burial",
        "ancient relic authenticity controversy",
        "forgery archaeological artifact",
        "ancient tablet translation controversy",
        "prehistoric monument purpose debate",
        "ancient civilization collapse mystery",
        "archaeological site discovery controversy",
        "ancient engineering feat controversy",
        "oopart controversy",
        "Baghdad Battery controversy",
        "Antikythera mechanism discovery",
        "Puma Punku controversy",
        "Baalbek stones controversy",
        "Nan Madol mystery",
        "Nazca Lines purpose debate",
        "Göbekli Tepe interpretation debate",
    ]
    for i in range(max_tries):
        q = random.choice(seed_queries)
        titles = wiki_search_titles(sess, q, limit=30)
        titles = [t for t in titles if is_candidate_title(t)]
        random.shuffle(titles)
        for t in titles[:14]:
            full = wiki_extract(sess, t, intro_only=False)
            if not full.strip():
                continue
            if is_oparts_like(t, full):
                vlog(f"선정 후보 통과: {t} (len={len(full)})")
                return t, full
        vlog(f"주제 탐색 실패({i+1}/{max_tries})")
    raise RuntimeError("주제 선정 실패(진부 회피/분량/키워드 조건)")


# =========================
# 트렌딩 질문
# =========================
def fetch_trending_google_questions() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    try:
        url = "https://trends.google.com/trends/api/dailytrends"
        params = {"hl": "en-US", "tz": "-540", "geo": "KR"}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        text = r.text
        if text.startswith("\ufeff"):
            text = text.lstrip("\ufeff")
        brace = text.find("{")
        if brace != -1:
            text = text[brace:]
        data = json.loads(text)
        for day in data.get("default", {}).get("trendingSearchesDays", []):
            for item in day.get("trendingSearches", []):
                title = item.get("title", {}).get("query")
                if title:
                    out.append({"en": title, "ko": title})
    except Exception:
        return []
    return out


def fetch_trending_naver_questions() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    try:
        url = "https://datalab.naver.com/keyword/realtimeList.naver"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        for m in re.finditer(r"<span class=\"title\">([^<]+)</span>", r.text):
            term = m.group(1).strip()
            if term:
                out.append({"en": term, "ko": term})
    except Exception:
        return []
    return out


def fetch_wikimedia_top_questions(sess: Optional[requests.Session] = None) -> List[Dict[str, str]]:
    s = sess or make_session()
    out: List[Dict[str, str]] = []
    try:
        yesterday = dt.date.today() - dt.timedelta(days=1)
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/"
            f"{yesterday.year}/{yesterday.month:02d}/{yesterday.day:02d}"
        )
        r = s.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", [{}])[0].get("articles", []):
            title = item.get("article")
            if title and not title.startswith("Special:"):
                q = title.replace("_", " ")
                out.append({"en": q, "ko": q})
    except Exception:
        return []
    return out


def refresh_question_pool(sess: Optional[requests.Session] = None) -> None:
    global FALLBACK_QUESTIONS
    sess = sess or make_session()
    google_q = fetch_trending_google_questions()
    naver_q = fetch_trending_naver_questions()
    wiki_q = fetch_wikimedia_top_questions(sess)
    combined = google_q + naver_q + wiki_q + FALLBACK_QUESTIONS
    seen = set()
    deduped: List[Dict[str, str]] = []
    for item in combined:
        key = (item.get("en") or item.get("ko") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append({"ko": item.get("ko", item.get("en", "")), "en": item.get("en", item.get("ko", ""))})
    FALLBACK_QUESTIONS = deduped
    vlog(f"질문 풀 갱신: {len(FALLBACK_QUESTIONS)}개")



# =========================
# GPT 대본 생성
# =========================
def extract_json_block(txt: str) -> dict:
    m = re.search(r"\{.*\}\s*$", txt, flags=re.S)
    if not m:
        raise RuntimeError("GPT 응답에서 JSON 블록을 찾지 못했습니다.")
    return json.loads(m.group(0))


def safe_json_loads(txt: str) -> dict:
    if not txt:
        raise RuntimeError("GPT 응답이 비어있습니다.")
    s = txt.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        return extract_json_block(s)
    except Exception:
        pass
    a = s.find("{")
    b = s.rfind("}")
    if a != -1 and b != -1 and b > a:
        core = s[a:b + 1]
        try:
            return json.loads(core)
        except Exception:
            core2 = re.sub(r",\s*([}\]])", r"\1", core)
            return json.loads(core2)
    raise RuntimeError("GPT 응답에서 JSON을 파싱하지 못했습니다.")


def estimate_tts_seconds_korean(text: str) -> float:
    chars = len(re.sub(r"\s+", "", text))
    return chars / 8.0


def estimate_final_seconds_from_script(script: Dict) -> float:
    scenes = script.get("scenes", []) or []
    total_raw = sum(estimate_tts_seconds_korean(sc.get("narration", "")) for sc in scenes)
    total_raw += TTS_LEADIN_S * len(scenes)
    est = total_raw / VOICE_SPEED
    est += float(END_PAD_S)
    return est


def build_script(client: OpenAI, title_en: str, wiki_text: str, adjust_note: str, image_candidates: List[str]) -> Dict:
    system = (
        "당신은 10년차 유튜브 숏츠 베테랑(고대미스터리/고고학)입니다. "
        "자료는 위키 텍스트(사실)만 사용합니다. "
        "단, 전달은 드라마틱하게: 정보 나열 금지, 매 씬 끝은 다음 단서가 궁금하게. "
        "첫 문장은 반드시 강한 훅. 씬 수는 {min_sc}~{max_sc}개.".format(min_sc=MIN_SCENES, max_sc=MAX_SCENES)
    )
    img_list_txt = "\n".join([f"{i+1}. {u}" for i, u in enumerate(image_candidates)])
    user = f"""문서 제목(영문): {title_en}

사용 가능한 이미지 후보(이 목록 안에서만 선택, 번호를 image_idx로 사용):
{img_list_txt}

위키 본문(사실 근거):
{wiki_text[:12000]}

필수 조건:
- 성우는 1.5배속으로 읽는다. 최종 영상 길이는 58~62초.
- 씬은 {MIN_SCENES}~{MAX_SCENES}개.
- scenes 각 항목에 image_idx(1부터 시작)를 반드시 넣어라.
- narration은 선택한 이미지가 화면에 나오는 것처럼 자연스럽게 묘사/연결하라.
- {adjust_note}

JSON만 출력:
{{
  "title_ko": "...",
  "title_en": "{title_en}",
  "mood": "mystery",
  "scenes": [
    {{"idx":1,"image_idx":1,"narration":"...","image_keywords_en":"..."}}
  ]
}}
"""
    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.7,
    )
    txt = (resp.output_text or "").strip()
    return safe_json_loads(txt)


def normalize_script(script: Dict) -> Dict:
    scenes = script.get("scenes", []) or []
    out = []
    for i, sc in enumerate(scenes, start=1):
        d = dict(sc)
        d["idx"] = int(d.get("idx", i))
        try:
            d["image_idx"] = int(d.get("image_idx", 0))
        except Exception:
            d["image_idx"] = 0
        d["narration"] = (d.get("narration") or "").strip()
        d["image_keywords_en"] = (d.get("image_keywords_en") or "").strip()
        out.append(d)
    out.sort(key=lambda x: x["idx"])
    for i, sc in enumerate(out, start=1):
        sc["idx"] = i
    script["scenes"] = out
    script["title_ko"] = shorten_title_to_fit((script.get("title_ko") or script.get("title_en") or "").strip(), max_chars=15)
    return script


def ensure_script_constraints(client: OpenAI, title_en: str, wiki_text: str, verbose: bool, image_candidates: List[str], tries: int = 4) -> Dict:
    note = "첫 문장은 강한 훅. 이미지-내러티브 정합."
    script = normalize_script(build_script(client, title_en, wiki_text, note, image_candidates))
    for _ in range(tries):
        scenes = script.get("scenes", []) or []
        n = len(scenes)
        est = estimate_final_seconds_from_script(script)
        bad_narr = any((not sc.get("narration")) for sc in scenes)
        bad_img = any((int(sc.get("image_idx") or 0) <= 0) for sc in scenes)
        vlog(f"체크: 씬={n}, 예상길이={est:.1f}s, 빈내레이션={bad_narr}, image_idx누락={bad_img}")
        if (MIN_SCENES <= n <= MAX_SCENES) and (TARGET_MIN <= est <= TARGET_MAX) and (not bad_narr) and (not bad_img):
            return script
        adjust = []
        if not (MIN_SCENES <= n <= MAX_SCENES):
            adjust.append(f"씬 수를 {MIN_SCENES}~{MAX_SCENES}로 맞춰라.")
        if est < TARGET_MIN:
            adjust.append("길이를 늘려라.")
        if est > TARGET_MAX:
            adjust.append("길이를 줄여라.")
        if bad_narr:
            adjust.append("모든 씬 narration을 채워라.")
        if bad_img:
            adjust.append("모든 씬에 image_idx를 지정하라.")
        script = normalize_script(build_script(client, title_en, wiki_text, " ".join(adjust), image_candidates))
    return script


# =========================
# 씬 추출 (강건)
# =========================
def _extract_from_obj(obj: Any, found: List[Dict[str, Any]]) -> None:
    if obj is None:
        return
    if isinstance(obj, str):
        text = obj.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9]*\n", "", text)
            text = text.rstrip("`")
        if text.startswith("{") and text.endswith("}"):
            try:
                loaded = json.loads(text)
                _extract_from_obj(loaded, found)
            except Exception:
                return
        return
    if isinstance(obj, dict):
        if "narration" in obj and "image_keywords_en" in obj:
            try:
                idx = int(obj.get("idx", len(found) + 1))
            except Exception:
                idx = len(found) + 1
            found.append({
                "idx": idx,
                "image_idx": obj.get("image_idx", 0),
                "narration": obj.get("narration", ""),
                "image_keywords_en": obj.get("image_keywords_en", ""),
            })
        for v in obj.values():
            _extract_from_obj(v, found)
        return
    if isinstance(obj, list):
        for item in obj:
            _extract_from_obj(item, found)
        return


def extract_scene_list(script: Any) -> Optional[List[Dict[str, Any]]]:
    found: List[Dict[str, Any]] = []
    _extract_from_obj(script, found)
    return found or None


# =========================
# Wikimedia/이미지/렌더링 보조
# =========================
def which_bin(name: str) -> Optional[str]:
    exe = shutil.which(name)
    if exe:
        return exe
    for c in [rf"C:\\ffmpeg\\bin\\{name}.exe", rf"C:\\Program Files\\ffmpeg\\bin\\{name}.exe"]:
        if Path(c).exists():
            return c
    return None


def which_ffmpeg(explicit: Optional[str]) -> str:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"ffmpeg 경로를 찾지 못했습니다: {explicit}")
    exe = which_bin("ffmpeg")
    if exe:
        return exe
    raise FileNotFoundError("ffmpeg를 찾지 못했습니다. --ffmpeg_path를 지정하세요.")


def run_cmd(cmd: List[str], verbose: bool) -> None:
    if verbose:
        vlog("CMD: " + " ".join(cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = "\n".join(p.stderr.splitlines()[-120:])
        raise RuntimeError(f"명령 실패(rc={p.returncode})\nCMD: {' '.join(cmd)}\n---- stderr ----\n{tail}")


def wiki_api_query(api: str, params: dict, timeout: int = 30) -> dict:
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    r = requests.get(api, params=params, timeout=timeout, headers={"User-Agent": "OPARTSShortsFactory/1.7"})
    r.raise_for_status()
    return r.json()


def wiki_get_lead_image_url(title: str, width: int = 1280, verbose: bool = False) -> Optional[str]:
    try:
        j = wiki_api_query(WIKI_API, {
            "action": "query",
            "prop": "pageimages",
            "titles": title,
            "pithumbsize": str(width),
            "pilicense": "any",
        })
        pages = (j.get("query", {}).get("pages", []) or [])
        if not pages:
            return None
        thumb = pages[0].get("thumbnail", {})
        return thumb.get("source")
    except Exception as e:
        if verbose:
            log(f"[wiki] lead image failed: {e}")
        return None


def wiki_list_article_files(title: str, verbose: bool = False) -> List[str]:
    files: List[str] = []
    try:
        cont = None
        while True:
            params = {
                "action": "query",
                "prop": "images",
                "titles": title,
                "imlimit": "max",
            }
            if cont:
                params["imcontinue"] = cont
            j = wiki_api_query(WIKI_API, params)
            pages = (j.get("query", {}).get("pages", []) or [])
            if pages:
                imgs = pages[0].get("images", []) or []
                for it in imgs:
                    t = (it.get("title") or "").strip()
                    if t.startswith("File:"):
                        files.append(t)
            cont = j.get("continue", {}).get("imcontinue")
            if not cont:
                break
        keep = []
        for t in files:
            tl = t.lower()
            if any(tl.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]):
                keep.append(t)
        return keep
    except Exception as e:
        if verbose:
            log(f"[wiki] list files failed: {e}")
        return []


def wiki_file_to_thumb_url(file_title: str, width: int = 1280, verbose: bool = False) -> Optional[str]:
    try:
        j = wiki_api_query(WIKI_API, {
            "action": "query",
            "prop": "imageinfo",
            "titles": file_title,
            "iiprop": "url|mime|size",
            "iiurlwidth": str(width),
        })
        pages = (j.get("query", {}).get("pages", []) or [])
        if not pages:
            return None
        ii = (pages[0].get("imageinfo", []) or [])
        if not ii:
            return None
        return ii[0].get("thumburl") or ii[0].get("url")
    except Exception as e:
        if verbose:
            log(f"[wiki] file thumb failed: {file_title} -> {e}")
        return None


def looks_like_map(file_title: str) -> bool:
    t = file_title.lower()
    keys = ["map", "locator", "location", "distribution", "route", "topographic", "relief"]
    if any(k in t for k in keys):
        return True
    if "svg" in t and ("map" in t or "locator" in t):
        return True
    return False


def wiki_collect_preferred_image_urls(title: str, need: int, verbose: bool = False) -> Tuple[List[str], Optional[str]]:
    urls: List[str] = []
    used = set()
    lead = wiki_get_lead_image_url(title, width=1280, verbose=verbose)
    if lead:
        urls.append(lead); used.add(lead)
    files = wiki_list_article_files(title, verbose=verbose)
    map_url = None
    for ft in files:
        if looks_like_map(ft):
            u = wiki_file_to_thumb_url(ft, width=1280, verbose=verbose)
            if u and u not in used:
                map_url = u
                urls.append(u); used.add(u)
                break
    for ft in files:
        if len(urls) >= need:
            break
        u = wiki_file_to_thumb_url(ft, width=1280, verbose=verbose)
        if u and u not in used:
            urls.append(u); used.add(u)
    return urls[:need], map_url


def commons_search_file_thumb(query: str, width: int = 1280, verbose: bool = False) -> Optional[str]:
    try:
        j = wiki_api_query(WIKI_API_COMMONS, {
            "action": "query",
            "list": "search",
            "srnamespace": "6",
            "srlimit": "10",
            "srsearch": query,
        })
        hits = (j.get("query", {}).get("search", []) or [])
        for h in hits:
            title = h.get("title")
            if not title or not title.startswith("File:"):
                continue
            jj = wiki_api_query(WIKI_API_COMMONS, {
                "action": "query",
                "prop": "imageinfo",
                "titles": title,
                "iiprop": "url|mime|size",
                "iiurlwidth": str(width),
            })
            pages = (jj.get("query", {}).get("pages", []) or [])
            if pages:
                ii = (pages[0].get("imageinfo", []) or [])
                if ii:
                    u = ii[0].get("thumburl") or ii[0].get("url")
                    if u:
                        return u
        return None
    except Exception as e:
        if verbose:
            log(f"[commons] search failed: {e}")
        return None


def fetch_pexels(pexels_key: str, query: str, per_page: int = 28) -> List[Dict]:
    headers = {"Authorization": pexels_key, "User-Agent": "OPARTSShortsFactory/1.6"}
    params = {"query": query, "per_page": per_page, "orientation": "portrait"}
    r = requests.get(PEXELS_URL, headers=headers, params=params, timeout=20)
    if r.status_code != 200:
        return []
    js = r.json()
    out = []
    for p in js.get("photos", []):
        out.append({"url": p.get("src", {}).get("large2x") or p.get("src", {}).get("large"), "alt": p.get("alt", "")})
    return [x for x in out if x.get("url")]


def fetch_pixabay(pixabay_key: str, query: str, per_page: int = 80) -> List[Dict]:
    params = {"key": pixabay_key, "q": query, "image_type": "photo", "orientation": "vertical", "per_page": per_page, "safesearch": "true"}
    r = requests.get(PIXABAY_URL, params=params, timeout=20, headers={"User-Agent": "OPARTSShortsFactory/1.6"})
    if r.status_code != 200:
        return []
    js = r.json()
    out = []
    for h in js.get("hits", []):
        out.append({"url": h.get("largeImageURL") or h.get("webformatURL"), "alt": h.get("tags", "")})
    return [x for x in out if x.get("url")]


def pick_best_stock_image(pexels_key: Optional[str], pixabay_key: Optional[str], keywords_en: str, verbose: bool) -> Optional[str]:
    q = (keywords_en or "").strip()
    if not q:
        return None
    hits: List[Dict] = []
    if pexels_key:
        hits += fetch_pexels(pexels_key, q)
    if pixabay_key:
        hits += fetch_pixabay(pixabay_key, q)
    if not hits:
        return None
    words = [w.lower() for w in re.split(r"[\s,]+", q) if w.strip()]

    def score(h: Dict) -> int:
        hay = (h.get("alt", "") or "").lower()
        return sum(1 for w in words if w in hay)

    hits.sort(key=score, reverse=True)
    vlog(f"스톡 이미지: q='{q}', score={score(hits[0])}")
    return hits[0].get("url")


def normalize_wikimedia_url(url: str, width: int = 1080) -> str:
    try:
        u = urlparse(url)
        host = (u.netloc or "").lower()
        path = u.path or ""
        if "wikimedia.org" not in host:
            return url
        filename = None
        if "/wikipedia/commons/thumb/" in path:
            parts = path.split("/")
            ti = None
            for i, p in enumerate(parts):
                if p == "thumb":
                    ti = i
                    break
            if ti is not None and len(parts) > ti + 3:
                filename = parts[ti + 3]
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


def make_placeholder_image(out_path: Path, text_msg: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1080, 1080
    img = Image.new("RGB", (w, h), (8, 8, 8))
    draw = ImageDraw.Draw(img)
    msg = (text_msg or "image unavailable").strip()
    wrapped = []
    line = ""
    for word in msg.split():
        if len(line) + len(word) + 1 > 24:
            wrapped.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        wrapped.append(line)
    wrapped = wrapped[:8]
    try:
        font = load_font(46)
    except Exception:
        font = None
    y = 120
    for ln in wrapped:
        bbox = draw.textbbox((0, 0), ln, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) // 2, y), ln, font=font, fill=(235, 235, 235))
        y += 70
    img.save(out_path, quality=92)


def cache_key_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def download_image(url: str, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 0:
        return True
    try:
        key = cache_key_for_url(url)
    except Exception:
        key = None
    cache_dir = out_path.parent.parent / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = (cache_dir / f"{key}.bin") if key else None
    if cache_path and cache_path.exists() and cache_path.stat().st_size > 0:
        try:
            out_path.write_bytes(cache_path.read_bytes())
            return True
        except Exception:
            pass
    url2 = normalize_wikimedia_url(url, width=1080)
    headers = {"User-Agent": "OPARTSShortsFactory/1.9 (educational; respectful rate-limit)"}
    sess = requests.Session()
    max_retry = 6
    for i in range(max_retry):
        try:
            r = sess.get(url2, timeout=30, headers=headers, stream=True)
            if r.status_code == 200:
                content = r.content
                out_path.write_bytes(content)
                if cache_path:
                    try:
                        cache_path.write_bytes(content)
                    except Exception:
                        pass
                time.sleep(random.uniform(0.8, 1.2))
                return True
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                try:
                    wait_s = float(ra) if ra else float(2 ** i)
                except Exception:
                    wait_s = float(2 ** i)
                wait_s = min(30.0, max(1.0, wait_s))
                time.sleep(wait_s)
                continue
            if r.status_code in (500, 502, 503, 504):
                time.sleep(min(10.0, 1.5 * (i + 1)))
                continue
            r.raise_for_status()
        except Exception:
            time.sleep(min(10.0, 1.5 * (i + 1)))
    try:
        make_placeholder_image(out_path, f"이미지 다운로드 실패: {url}")
    except Exception:
        pass
    return False


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
    for i, sc in enumerate(scenes, start=1):
        idx = int(sc.get("idx", i))
        kw = (sc.get("image_keywords_en") or "").strip()
        query = kw or title_en
        image_idx = 0
        try:
            image_idx = int(sc.get("image_idx") or 0)
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


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        FONT_DIR / "GmarketSansTTFBold.ttf",
        FONT_DIR / "Pretendard-Bold.ttf",
        Path(r"C:\\Windows\\Fonts\\malgunbd.ttf"),
        Path(r"C:\\Windows\\Fonts\\malgun.ttf"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return ImageFont.truetype(str(p), size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def apply_watermark(img_path: Path, text: str = "araboza") -> None:
    try:
        img = Image.open(img_path).convert("RGBA")
    except Exception:
        return
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rect_h = max(60, int(h * 0.08))
    rect_y = h - rect_h - 20
    draw.rectangle([(40, rect_y), (w - 40, rect_y + rect_h)], fill=(0, 0, 0, 170))
    font = load_font(max(42, rect_h // 2))
    tw = draw.textlength(text, font=font)
    th = font.getbbox(text)[3] - font.getbbox(text)[1]
    tx = w - tw - 70
    ty = rect_y + (rect_h - th) // 2
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 240))
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(img_path)


def enhance_mood(im: Image.Image, mood: str = "mystery") -> Image.Image:
    m = (mood or "").lower()
    im = im.convert("RGB")
    im = im.filter(ImageFilter.GaussianBlur(radius=0.35))
    if "archaeology" in m or "history" in m or "civilization" in m:
        b = 0.95
        c = 0.90
        k = 1.08
    else:
        b = 0.88
        c = 0.75
        k = 1.15
    im = ImageEnhance.Brightness(im).enhance(b)
    im = ImageEnhance.Color(im).enhance(c)
    im = ImageEnhance.Contrast(im).enhance(k)
    return im


def blur_extend(im: Image.Image, width: int, height: int) -> Image.Image:
    bg = im.convert("RGB")
    iw, ih = bg.size
    scale = max(width / iw, height / ih)
    bg = bg.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    left = (bg.size[0] - width) // 2
    top = (bg.size[1] - height) // 2
    bg = bg.crop((left, top, left + width, top + height))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=22))
    bg = ImageEnhance.Brightness(bg).enhance(0.83)
    fg = im.convert("RGB")
    scale2 = min(width / iw, height / ih)
    fg = fg.resize((max(1, int(iw * scale2)), max(1, int(ih * scale2))), Image.LANCZOS)
    canvas = bg.copy()
    px = (width - fg.size[0]) // 2
    py = (height - fg.size[1]) // 2
    canvas.paste(fg, (px, py))
    return canvas


def _wrap_title_two_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if " " in text:
        words = text.split(" ")
        if len(words) <= 3 and draw.textlength(text, font=font) <= max_w:
            return [text]
        best = None
        for i in range(1, len(words)):
            l1 = " ".join(words[:i]).strip()
            l2 = " ".join(words[i:]).strip()
            if not l1 or not l2:
                continue
            w1 = draw.textlength(l1, font=font)
            w2 = draw.textlength(l2, font=font)
            if w1 > max_w or w2 > max_w:
                continue
            score = abs(w1 - w2)
            if len(words[:i]) == 1:
                score += 1200
            if len(words[i:]) == 1:
                score += 5000
            cand = (score, [l1, l2])
            if best is None or cand[0] < best[0]:
                best = cand
        if best:
            return best[1]
        lines: List[str] = []
        cur = ""
        for w in words:
            cand = (cur + " " + w).strip() if cur else w
            if draw.textlength(cand, font=font) <= max_w:
                cur = cand
            else:
                if cur:
                    lines.append(cur)
                cur = w
            if len(lines) >= 2:
                break
        if cur and len(lines) < 2:
            lines.append(cur)
        return lines[:2]
    chars = list(text)
    lines: List[str] = []
    cur = ""
    for ch in chars:
        cand = cur + ch
        if draw.textlength(cand, font=font) <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = ch
        if len(lines) >= 2:
            break
    if cur and len(lines) < 2:
        lines.append(cur)
    return lines


def draw_title_centered_in_topbar(img: Image.Image, title: str) -> Image.Image:
    alpha = int(max(0, min(255, TOP_BAR_ALPHA * 255)))
    bar = Image.new("RGBA", (W, TITLE_BOX_H), (0, 0, 0, alpha))
    im_rgba = img.convert("RGBA")
    im_rgba.alpha_composite(bar, (0, 0))
    im = im_rgba.convert("RGB")
    draw = ImageDraw.Draw(im)
    raw = (title or "").strip()
    if not raw:
        return im
    text = re.sub(r"\s+", " ", raw).strip()
    text = shorten_title_to_fit(text, max_chars=15)
    max_w = W - SAFE_X * 2
    best_size = 44
    best_lines = [text]
    for size in range(96, 43, -2):
        font = load_font(size)
        lines = text.splitlines() if "\n" in text else _wrap_title_two_lines(draw, text, font, max_w)
        if not lines or len(lines) > 2:
            continue
        widths = [draw.textlength(ln, font=font) for ln in lines]
        if max(widths) <= max_w:
            best_size = size
            best_lines = lines
            break
    font = load_font(best_size)
    line_gap = int(best_size * 0.18)
    bboxes = [draw.textbbox((0, 0), ln, font=font, stroke_width=TITLE_STROKE_W) for ln in best_lines]
    heights = [(bb[3] - bb[1]) for bb in bboxes]
    total_h = sum(heights) + line_gap * (len(best_lines) - 1)
    y = (TITLE_BOX_H - total_h) / 2
    for ln, h in zip(best_lines, heights):
        tw = draw.textlength(ln, font=font)
        x = (W - tw) / 2
        draw.text((x, y), ln, font=font, fill=TITLE_COLOR, stroke_width=TITLE_STROKE_W, stroke_fill=TITLE_STROKE)
        y += h + line_gap
    return im


def fit_image_to_area_bottom(im: Image.Image, area_w: int, area_h: int) -> Image.Image:
    im = im.convert("RGB")
    return ImageOps.fit(im, (area_w, area_h), method=Image.LANCZOS, centering=(0.5, 1.0))


def render_frame(image_path: Path, title_ko: str, out_png: Path, mood: str, verbose: bool) -> None:
    im0 = Image.open(image_path).convert("RGB")
    area_h = H - TITLE_BOX_H
    img_layer = fit_image_to_area_bottom(im0, W, area_h)
    img_layer = enhance_mood(img_layer, mood=mood)
    title_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bar = Image.new("RGBA", (W, TITLE_BOX_H), (0, 0, 0, 255))
    title_layer.paste(bar, (0, 0))
    title_rgb = Image.new("RGB", (W, H), (0, 0, 0))
    title_rgb = draw_title_centered_in_topbar(title_rgb, title_ko)
    title_crop = title_rgb.crop((0, 0, W, TITLE_BOX_H)).convert("RGBA")
    title_layer.alpha_composite(title_crop, (0, 0))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img_png = out_png.with_name(out_png.stem + "_img.png")
    title_png = out_png.with_name(out_png.stem + "_title.png")
    img_layer.save(img_png, "PNG")
    title_layer.save(title_png, "PNG")
    base = Image.new("RGB", (W, H), (0, 0, 0))
    base.paste(img_layer, (0, TITLE_BOX_H))
    base_rgba = base.convert("RGBA")
    base_rgba.alpha_composite(title_layer)
    base_rgba.convert("RGB").save(out_png, "PNG")
    vlog(f"프레임 생성: {out_png.name}")


# =========================
# 오디오 / TTS
# =========================
def duration_seconds(ffmpeg: str, media: Path) -> float:
    ffprobe = which_bin("ffprobe")
    if ffprobe:
        p = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(media)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        try:
            return float(p.stdout.strip())
        except Exception:
            pass
    p = subprocess.run([ffmpeg, "-i", str(media)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", p.stderr)
    if not m:
        return 0.0
    hh, mm, ss, frac = m.groups()
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(frac) / 100.0


def tts_scene_to_wav_speed(client: OpenAI, ffmpeg: str, text: str, out_wav: Path, verbose: bool) -> float:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    raw_mp3 = out_wav.with_suffix(".raw.mp3")
    try:
        resp = client.audio.speech.create(model=TTS_MODEL, voice=TTS_VOICE, input=text, response_format="mp3")
    except TypeError:
        resp = client.audio.speech.create(model=TTS_MODEL, voice=TTS_VOICE, input=text)
    if hasattr(resp, "write_to_file"):
        resp.write_to_file(str(raw_mp3))
    else:
        raw_mp3.write_bytes(bytes(resp))
    lead_wav = out_wav.with_suffix(".lead.wav")
    run_cmd([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{TTS_LEADIN_S}", str(lead_wav)], verbose=False)
    tmp_wav = out_wav.with_suffix(".tmp.wav")
    run_cmd([ffmpeg, "-y", "-i", str(raw_mp3), "-filter:a", f"atempo={VOICE_SPEED}", "-ar", "48000", "-ac", "2", str(tmp_wav)], verbose=False)
    run_cmd([ffmpeg, "-y", "-i", str(lead_wav), "-i", str(tmp_wav), "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]", "-map", "[a]", "-ar", "48000", "-ac", "2", str(out_wav)], verbose=False)
    for q in [raw_mp3, lead_wav, tmp_wav]:
        try:
            q.unlink()
        except Exception:
            pass
    dur = duration_seconds(ffmpeg, out_wav)
    if dur <= 0.01:
        dur = max(0.25, estimate_tts_seconds_korean(text) / VOICE_SPEED)
    vlog(f"TTS 길이={dur:.2f}s")
    return dur


def concat_audio_wavs(ffmpeg: str, wavs: List[Path], out_wav: Path, verbose: bool) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if not wavs:
        raise RuntimeError("concat_audio_wavs: 입력 wav가 없습니다.")
    if len(wavs) == 1:
        shutil.copyfile(wavs[0], out_wav)
        return
    args = [ffmpeg, "-y"]
    for w in wavs:
        args += ["-i", str(w)]
    ins = "".join([f"[{i}:a]" for i in range(len(wavs))])
    fc = f"{ins}concat=n={len(wavs)}:v=0:a=1[a]"
    args += ["-filter_complex", fc, "-map", "[a]", "-ar", "48000", "-ac", "2", str(out_wav)]
    run_cmd(args, verbose)


def normalize_voice_loudness(ffmpeg: str, voice_in: Path, voice_out: Path, verbose: bool) -> None:
    voice_out.parent.mkdir(parents=True, exist_ok=True)
    run_cmd([ffmpeg, "-y", "-i", str(voice_in), "-filter:a", "dynaudnorm=f=150:g=9:p=0.5, loudnorm=I=-16:TP=-1.5:LRA=11, alimiter=limit=0.97, afade=t=in:st=0:d=0.05", "-ar", "48000", "-ac", "2", str(voice_out)], verbose)


# =========================
# 비디오(무음 씬) / concat / 믹스
# =========================
def zoompan_filter(seed: int, duration_s: float) -> str:
    rnd = random.Random(seed)
    d = max(1, int(round(max(0.2, float(duration_s)) * FPS)))
    dur = max(0.2, float(duration_s))
    if dur <= 1.0:
        z0, z1 = 1.03, 1.30
    elif dur <= 2.0:
        z0, z1 = 1.02, 1.25
    elif dur <= 4.0:
        z0, z1 = 1.02, 1.20
    else:
        z0, z1 = 1.01, 1.16
    mode = rnd.choice(["center", "lr", "rl", "ud", "du", "diag1", "diag2"])
    if mode == "center":
        px0 = px1 = 0.50
        py0 = py1 = 0.60
    elif mode == "lr":
        px0, px1 = 0.12, 0.88
        py0 = py1 = rnd.uniform(0.45, 0.70)
    elif mode == "rl":
        px0, px1 = 0.88, 0.12
        py0 = py1 = rnd.uniform(0.45, 0.70)
    elif mode == "ud":
        px0 = px1 = rnd.uniform(0.30, 0.70)
        py0, py1 = 0.35, 0.80
    elif mode == "du":
        px0 = px1 = rnd.uniform(0.30, 0.70)
        py0, py1 = 0.80, 0.35
    elif mode == "diag1":
        px0, px1 = 0.18, 0.82
        py0, py1 = 0.40, 0.78
    else:
        px0, px1 = 0.82, 0.18
        py0, py1 = 0.40, 0.78
    denom = max(1, d - 1)
    p = f"(on/{denom})"
    z = f"({z0:.3f} + ({z1:.3f}-{z0:.3f})*{p})"
    px = f"({px0:.4f} + ({px1:.4f}-{px0:.4f})*{p})"
    py = f"({py0:.4f} + ({py1:.4f}-{py0:.4f})*{p})"
    x = f"(iw - iw/zoom)*{px}"
    y = f"(ih - ih/zoom)*{py}"
    return (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='{z}':d={d}:x='{x}':y='{y}':s={W}x{H}:fps={FPS}"
    )


def make_scene_video_silent(ffmpeg: str, frame_png: Path, duration_s: float, out_mp4: Path, seed: int, mood: str, verbose: bool) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    m = (mood or "").lower()
    if "archaeology" in m or "history" in m or "civilization" in m:
        mood_vf = "eq=contrast=1.05:brightness=0.02:saturation=0.95"
    else:
        mood_vf = "eq=contrast=1.10:brightness=-0.02:saturation=0.85"
    img_png = frame_png.with_name(frame_png.stem + "_img.png")
    title_png = frame_png.with_name(frame_png.stem + "_title.png")
    area_h = H - TITLE_BOX_H
    if img_png.exists() and title_png.exists():
        img_vf = zoompan_filter(seed, duration_s) + "," + mood_vf + f",scale={W}:{area_h}:force_original_aspect_ratio=increase,crop={W}:{area_h}"
        filter_complex = (
            f"[0:v]{img_vf}[img];"
            f"color=c=black:s={W}x{H}:r={FPS}:d={max(0.2, duration_s):.3f}[bg];"
            f"[bg][img]overlay=0:{TITLE_BOX_H}:shortest=1[base];"
            f"[1:v]format=rgba[title];"
            f"[base][title]overlay=0:0:shortest=1[outv]"
        )
        run_cmd([
            ffmpeg, "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(img_png),
            "-loop", "1", "-framerate", str(FPS), "-i", str(title_png),
            "-t", f"{max(0.2, duration_s):.3f}",
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(out_mp4)
        ], verbose)
    else:
        vf = zoompan_filter(seed, duration_s) + "," + mood_vf
        run_cmd([
            ffmpeg, "-y",
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(frame_png),
            "-t", f"{max(0.2, duration_s):.3f}",
            "-vf", vf,
            "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(out_mp4)
        ], verbose)


def concat_videos(ffmpeg: str, mp4s: List[Path], out_mp4: Path, verbose: bool) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_mp4.with_suffix(".concat.txt")
    list_file.write_text("\n".join([f"file '{p.resolve().as_posix()}'" for p in mp4s]), encoding="utf-8")
    run_cmd([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out_mp4)], verbose)


def mux_audio_and_bgm(ffmpeg: str, video_in: Path, voice_wav_norm: Path, out_mp4: Path, verbose: bool) -> None:
    if not BGM_FIXED.exists():
        raise FileNotFoundError(f"bgm 파일을 찾지 못했습니다: {BGM_FIXED}")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    voice_dur = duration_seconds(ffmpeg, voice_wav_norm)
    if voice_dur <= 0.01:
        voice_dur = 1.0
    total_dur = voice_dur + END_PAD_S
    fade = min(BGM_FADE_S, max(0.2, END_PAD_S))
    fc = (
        f"[0:v]tpad=stop_mode=clone:stop_duration={END_PAD_S}[v];"
        f"[1:a]apad=pad_dur={END_PAD_S},volume=1.0[a1];"
        f"[2:a]atrim=0:{total_dur},volume=0.18,"
        f"afade=t=out:st={max(0.0, total_dur-fade):.3f}:d={fade:.3f}[a2];"
        f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=1[a]"
    )
    run_cmd([
        ffmpeg, "-y",
        "-i", str(video_in),
        "-i", str(voice_wav_norm),
        "-stream_loop", "-1", "-i", str(BGM_FIXED),
        "-filter_complex", fc,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4)
    ], verbose)


# =========================
# 자막
# =========================
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


def split_korean_caption_chunks(text: str, max_len: int = 20) -> List[str]:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    if t[-1] not in ".!?…":
        t += "."
    parts = re.split(r"(?<=[\.\!\?…])\s+", t)
    parts = [p.strip() for p in parts if p.strip()]
    out: List[str] = []
    clause_split = r"(?<=[,，])\s+|\s+(?:그리고|그런데|하지만|그래서|또는|게다가|결국|오히려|즉|다만|특히|바로|한편|반대로)\s+"
    for p in parts:
        if len(p) <= max_len:
            out.append(p)
            continue
        subparts = re.split(clause_split, p)
        subparts = [s.strip() for s in subparts if s.strip()]
        buf = ""
        for sp in subparts:
            cand = (buf + " " + sp).strip() if buf else sp
            if len(cand) <= max_len:
                buf = cand
            else:
                if buf:
                    out.append(buf)
                buf = sp
        if buf:
            out.append(buf)
    final: List[str] = []
    for p in out:
        p = p.strip()
        if len(p) <= max_len:
            final.append(p)
            continue
        words = p.split(" ")
        line = ""
        for w in words:
            cand = (line + " " + w).strip() if line else w
            if len(cand) <= max_len:
                line = cand
            else:
                if line:
                    final.append(line)
                line = w
        if line:
            final.append(line)
    merged: List[str] = []
    for c in final:
        c = c.strip()
        if not c:
            continue
        if merged and len(c) <= 3:
            merged[-1] = (merged[-1] + " " + c).strip()
        else:
            merged.append(c)
    cleaned: List[str] = []
    for c in merged:
        if cleaned and len(c) <= 1:
            cleaned[-1] = (cleaned[-1] + " " + c).strip()
        else:
            cleaned.append(c)
    return cleaned


def allocate_chunk_times(scene_dur: float, chunks: List[str], min_chunk: float = 0.45) -> List[float]:
    if not chunks:
        return []
    max_chunks = max(1, int(scene_dur / min_chunk))
    if len(chunks) > max_chunks:
        merged = []
        buf = ""
        for c in chunks:
            if not buf:
                buf = c
            elif len(merged) + 1 < max_chunks:
                merged.append(buf)
                buf = c
            else:
                buf = (buf + " " + c).strip()
        if buf:
            merged.append(buf)
        chunks = merged
    weights = [max(1, len(re.sub(r"\s+", "", c))) for c in chunks]
    total = float(sum(weights))
    times = [scene_dur * (w / total) for w in weights]
    times = [max(min_chunk, t) for t in times]
    s = sum(times)
    if s > 0:
        scale = scene_dur / s
        times = [t * scale for t in times]
    diff = scene_dur - sum(times)
    times[-1] += diff
    return times


def write_ass_subtitles_sentence_style(ass_path: Path, scenes: List[Dict], durations: List[float]) -> None:
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    sub_y = int(H * 0.74)
    font_name = "Malgun Gothic"
    font_size = 82
    outline = 8
    shadow = 1
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        f"-1,-1,0,0,100,100,0,0,1,{outline},{shadow},5,0,0,0,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    t = 0.0
    lines = [header]
    for i, sc in enumerate(scenes):
        scene_dur = durations[i] if i < len(durations) else 0.0
        scene_start = t
        scene_end = scene_start + max(0.2, scene_dur)
        lead = float(TTS_LEADIN_S) if scene_dur > 0.1 else 0.0
        cap_start = scene_start + min(lead, max(0.0, scene_dur - 0.05))
        cap_dur = max(0.2, scene_end - cap_start)
        narration = (sc.get("narration") or "").strip()
        chunks = split_korean_caption_chunks(narration, max_len=20)
        chunk_times = allocate_chunk_times(cap_dur, chunks, min_chunk=0.45)
        tt = cap_start
        for c, dt_s in zip(chunks, chunk_times):
            start = tt
            end = min(scene_end, start + max(0.08, float(dt_s)))
            tt = end
            txt = ass_escape(c)
            override = f"{{\\an5\\pos({W//2},{sub_y})}}"
            lines.append(f"Dialogue: 0,{fmt_ass_time(start)},{fmt_ass_time(end)},Default,,0,0,0,,{override}{txt}\n")
        t = scene_end
    ass_path.write_text("".join(lines), encoding="utf-8")


def burn_subtitles_only(ffmpeg: str, video_in: Path, ass_path: Path, out_mp4: Path, verbose: bool) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    ass_arg = str(ass_path).replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{ass_arg}'"
    run_cmd([ffmpeg, "-y", "-i", str(video_in), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out_mp4)], verbose)


# =========================
# 대본 실패 시 대체 생성
# =========================
def generate_fallback_script(question_ko: str, question_en: str) -> Dict[str, Any]:
    sess = make_session()
    titles = wiki_search_titles(sess, question_en, limit=5)
    title = titles[0] if titles else question_en
    text_ko = wiki_extract(sess, title, intro_only=True)
    if not text_ko.strip():
        text_ko = wiki_extract(sess, question_ko, intro_only=True)
    if not text_ko.strip():
        text_ko = question_ko
    sentences = [s.strip() for s in re.split(r"(?<=[\.\!\?…])\s+", text_ko) if s.strip()]
    if not sentences:
        sentences = [text_ko]
    scenes = []
    prefix = f"오늘은 {question_ko}에 대해 알아보자~"
    all_sent = [prefix] + sentences
    for i, s in enumerate(all_sent, start=1):
        narration = s
        if i == len(all_sent):
            if not narration.endswith("출처: 위키백과"):
                narration = narration.rstrip(". ") + " 출처: 위키백과"
        scenes.append({
            "idx": i,
            "image_idx": min(i, MAX_SCENES),
            "narration": narration,
            "image_keywords_en": question_en,
        })
    return {
        "title_en": question_en,
        "title_ko": shorten_title_to_fit(question_ko, 15),
        "mood": "mystery",
        "scenes": scenes[:MAX_SCENES],
    }


# =========================
# 성공 시 정리
# =========================
def cleanup_success(workdir: Path) -> None:
    final = workdir / "final.mp4"
    script_json = workdir / "script.json"
    images = workdir / "images"
    keep = {final.resolve(), script_json.resolve()}
    if images.exists():
        for p in images.rglob("*"):
            if p.is_file():
                keep.add(p.resolve())
    for p in workdir.rglob("*"):
        try:
            if p.is_file():
                rp = p.resolve()
                if rp in keep:
                    continue
                if p.suffix.lower() in {".mp3", ".mp4", ".wav"}:
                    p.unlink()
        except Exception:
            pass
    for p in sorted([x for x in workdir.rglob("*") if x.is_dir()], key=lambda x: len(str(x)), reverse=True):
        if p == images:
            continue
        try:
            if not any(p.iterdir()):
                p.rmdir()
        except Exception:
            pass


# =========================
# 파이프라인
# =========================
def generate_script(client: OpenAI, title_en: str, wiki_text: str, verbose: bool, cand_urls: List[str]) -> Dict[str, Any]:
    return ensure_script_constraints(client, title_en, wiki_text, verbose, cand_urls)


def pipeline_run(base_dir: Path, out_dir: Path, ffmpeg_path: Optional[str], verbose: bool, dry_run: bool = False) -> Tuple[Path, Path]:
    global VERBOSE
    VERBOSE = bool(verbose)
    if load_dotenv:
        load_dotenv(base_dir / ".env")
        load_dotenv()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 없습니다(.env 또는 환경변수).")
    pexels_key = (os.getenv("PEXELS_API_KEY") or "").strip() or None
    pixabay_key = (os.getenv("PIXABAY_API_KEY") or "").strip() or None
    ffmpeg = None if dry_run else which_ffmpeg(ffmpeg_path)
    if not dry_run and not BGM_FIXED.exists():
        raise FileNotFoundError(f"요청하신 bgm(mystery.mp3)을 찾지 못했습니다: {BGM_FIXED}")
    sp = load_feedback()
    log(f"시작 (성우={TTS_VOICE}, 배속={VOICE_SPEED}, 씬={MIN_SCENES}~{MAX_SCENES})")
    sess = make_session()
    refresh_question_pool(sess)
    log("주제 찾는 중(진부 회피)...")
    t0 = time.time()
    title_en, wiki_text = pick_topic(sess, verbose)
    lock_s = time.time() - t0
    log(f"주제 확정: {title_en} (소요 {lock_s:.1f}초)")
    sp = apply_time_feedback(sp, lock_s)
    save_feedback(sp)
    client = OpenAI(api_key=api_key)
    wiki_urls, map_url = wiki_collect_preferred_image_urls(title_en, need=MAX_SCENES, verbose=verbose)
    cand_urls: List[str] = []
    used = set()
    if map_url:
        cand_urls.append(map_url); used.add(map_url)
    for u in (wiki_urls or []):
        if u and u not in used:
            cand_urls.append(u); used.add(u)
        if len(cand_urls) >= MAX_SCENES:
            break
    if len(cand_urls) < MAX_SCENES:
        extra_q = title_en
        while len(cand_urls) < MAX_SCENES:
            u = commons_search_file_thumb(extra_q, width=1280, verbose=verbose)
            if not u or u in used:
                break
            cand_urls.append(u); used.add(u)
    log("대본 생성(훅/서사 강화)...")
    try:
        script = generate_script(client, title_en, wiki_text, verbose, cand_urls)
    except Exception as e:
        log(f"대본 생성 실패, 대체 대본 사용: {e}", level="WARN")
        script = generate_fallback_script(title_en, title_en)
    scenes_valid = extract_scene_list(script)
    if not scenes_valid:
        log("씬 추출 실패, 대체 대본 사용", level="WARN")
        script = generate_fallback_script(title_en, title_en)
        scenes_valid = extract_scene_list(script)
    mood_str = (script.get("mood") or "mystery").strip()
    title_ko = refine_title_ko(client, script.get("title_ko") or title_en, max_chars=15)
    script["title_ko"] = title_ko
    script["scenes"] = script.get("scenes") or scenes_valid or []
    scenes = script.get("scenes", []) or []
    if not scenes:
        script = generate_fallback_script(title_en, title_en)
        scenes = script.get("scenes", [])
    workdir = make_out_dir(out_dir, title_en)
    log(f"저장 폴더: {workdir}")
    if dry_run:
        (workdir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        entries = attribution_entries_from_script(scenes, cand_urls, map_url, title_en)
        write_media_attribution(workdir / "media_attribution.json", entries, dry_run=True)
        log("dry-run completed: script.json + media_attribution.json")
        return workdir / "script.json", workdir
    scene_mp4s: List[Path] = []
    scene_wavs: List[Path] = []
    durations: List[float] = []
    media_entries: List[Dict[str, Any]] = []
    log(f"씬 생성({len(scenes)}개)...")
    for i, sc in enumerate(scenes, start=1):
        idx = int(sc.get("idx", i))
        narration = (sc.get("narration") or "").strip() or "지금부터 기록에 남은 사실만, 빠르게 이어갑니다."
        kw = (sc.get("image_keywords_en") or "").strip()
        img_url: Optional[str] = None
        try:
            image_idx = int(sc.get("image_idx") or 0)
        except Exception:
            image_idx = 0
        selection = "placeholder"
        if 1 <= image_idx <= len(cand_urls):
            img_url = cand_urls[image_idx - 1]
            selection = "script_image_idx"
        if map_url and idx == 1 and len(cand_urls) >= 1:
            img_url = cand_urls[0]
            selection = "map_first_scene"
        if not img_url:
            q = kw or title_en
            img_url = commons_search_file_thumb(q, width=1280, verbose=verbose)
            selection = "commons_search" if img_url else "stock_fallback"
            if not img_url:
                img_url = pick_best_stock_image(pexels_key, pixabay_key, kw or title_en, verbose)
                selection = "stock_fallback" if img_url else "placeholder"
        img_path = workdir / "images" / f"{idx:02d}.jpg"
        media_entries.append(media_attribution_entry(idx, f"images/{idx:02d}.jpg", img_url, selection, kw or title_en))
        if img_url:
            download_image(img_url, img_path)
        else:
            make_placeholder_image(img_path, "이미지 없음")
        apply_watermark(img_path, text="araboza")
        frame_png = workdir / "frames" / f"{idx:02d}.png"
        render_frame(img_path, title_ko, frame_png, mood_str, verbose)
        wav = workdir / "tts" / f"{idx:02d}.wav"
        dur = tts_scene_to_wav_speed(client, ffmpeg, narration, wav, verbose)
        scene_wavs.append(wav)
        durations.append(dur)
        mp4 = workdir / "scenes" / f"{idx:02d}.mp4"
        make_scene_video_silent(ffmpeg, frame_png, dur, mp4, seed=idx * 9973, mood=mood_str, verbose=verbose)
        scene_mp4s.append(mp4)
    log("영상 합치는 중...")
    concat_video = workdir / "video_concat.mp4"
    concat_videos(ffmpeg, scene_mp4s, concat_video, verbose)
    log("목소리 합치는 중...")
    voice_wav = workdir / "voice.wav"
    concat_audio_wavs(ffmpeg, scene_wavs, voice_wav, verbose)
    log("목소리 볼륨 정규화 중...")
    voice_norm = workdir / "voice_norm.wav"
    normalize_voice_loudness(ffmpeg, voice_wav, voice_norm, verbose)
    log("BGM 합치는 중...")
    mixed = workdir / "mixed.mp4"
    mux_audio_and_bgm(ffmpeg, concat_video, voice_norm, mixed, verbose)
    log("자막 넣는 중(대본=성우 싱크)...")
    ass_path = workdir / "subs.ass"
    write_ass_subtitles_sentence_style(ass_path, scenes, durations)
    final = workdir / "final.mp4"
    burn_subtitles_only(ffmpeg, mixed, ass_path, final, verbose)
    (workdir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    write_media_attribution(workdir / "media_attribution.json", media_entries, dry_run=False)
    total = duration_seconds(ffmpeg, final)
    log(f"완료: final.mp4 (길이 {total:.1f}초)")
    if not (TARGET_MIN <= total <= TARGET_MAX):
        log(f"경고: 길이가 목표({TARGET_MIN}-{TARGET_MAX}초) 범위를 벗어났습니다.", level="WARN")
    return final, workdir


# =========================
# CLI
# =========================
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", nargs="?", default="run", choices=["run"])
    p.add_argument("--base_dir", default=str(BASE_DIR))
    p.add_argument("--out_dir", default=str(OUT_DIR))
    p.add_argument("--ffmpeg_path", default=None)
    p.add_argument("--dry_run", action="store_true", help="Generate script and media attribution metadata without rendering media.")
    p.add_argument("--verbose", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()
    workdir: Optional[Path] = None
    try:
        final, workdir = pipeline_run(Path(args.base_dir), Path(args.out_dir), args.ffmpeg_path, args.verbose, dry_run=args.dry_run)
        if args.dry_run:
            log("dry-run output kept: script.json + media_attribution.json")
            return
        else:
            cleanup_success(workdir)
        log("정리 완료: final.mp4 + script.json + images만 남겼습니다.")
    except Exception as e:
        log(str(e), level="ERROR")
        if workdir:
            log(f"실패로 중간 산출물을 보존합니다: {workdir}", level="WARN")
        raise


if __name__ == "__main__":
    main()
