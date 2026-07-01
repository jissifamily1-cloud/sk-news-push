# -*- coding: utf-8 -*-
"""SK 뉴스푸시 공용 엔진 — 키워드 + 상세키워드 매칭 → 텔레그램 발송.

모니터 선택: 환경변수 CONFIG=<configs 모듈명> (예: CONFIG=sk_issue)
  → configs/<CONFIG>.py 의 키워드/상세키워드/CHAT_ID 로 동작.

매칭 규칙 (LLM 미사용):
  제목(+요약)에서
    · REQUIRE_GROUPS 의 '각 그룹'마다 1개 이상 포함  (그룹 간 AND, 그룹 내 OR)
    · EXCLUDE_KEYWORDS 는 하나도 없을 것
    · 스포츠/게임(BLOCK) 아닐 것
  을 모두 만족하면 발송.

  예) SK 패밀리 = REQUIRE_GROUPS [ [오너家 13인], [SK·에스케이·SK그룹] ]
      → (이름 1명) 그리고 (SK 언급) 둘 다 있어야 발송.

환경변수:
  CONFIG (필수, 모니터 선택)
  TELEGRAM_BOT_TOKEN (필수)            ← GitHub Secrets
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET ← GitHub Secrets
  DRY_RUN=1 이면 발송 생략(테스트), TELEGRAM_CHAT_ID 로 chat_id 덮어쓰기 가능
"""

import importlib
import json
import os
import re
import sys
import time
import html as html_mod
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import common

# ── 모니터 설정 로드 ───────────────────────────────────────
CONFIG_NAME = os.environ.get("CONFIG", "").strip()
if not CONFIG_NAME:
    print("ERROR: 환경변수 CONFIG 미설정 (예: CONFIG=sk_issue)")
    sys.exit(1)
cfg = importlib.import_module("configs." + CONFIG_NAME)

NAME = cfg.NAME
SEARCH_QUERIES = cfg.SEARCH_QUERIES
REQUIRE_GROUPS = cfg.REQUIRE_GROUPS
EXCLUDE_KEYWORDS = getattr(cfg, "EXCLUDE_KEYWORDS", [])
# chat_id: 환경변수(TELEGRAM_CHAT_ID)가 있으면 우선(테스트방 전환용), 없으면 config 값
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or str(cfg.CHAT_ID)

# 공용 설정
BLOCK_KEYWORDS = common.BLOCK_KEYWORDS
BLOCK_DOMAINS = common.BLOCK_DOMAINS
BLOCK_URL_KEYWORDS = common.BLOCK_URL_KEYWORDS
WORD_BOUNDARY_KEYWORDS = common.WORD_BOUNDARY_KEYWORDS
MATCH_IN_DESCRIPTION = common.MATCH_IN_DESCRIPTION
ALLOW_ALL_PRESS = common.ALLOW_ALL_PRESS
ALLOW_DOMAINS = common.ALLOW_DOMAINS
ACTIVE_START_HOUR = common.ACTIVE_START_HOUR
ACTIVE_END_HOUR = common.ACTIVE_END_HOUR
RECENCY_MINUTES = common.RECENCY_MINUTES
FETCH_COUNT = common.FETCH_COUNT
FETCH_COUNT_NIGHT = common.FETCH_COUNT_NIGHT
MAX_SEEN_URLS = common.MAX_SEEN_URLS
MAX_SEND_PER_RUN = common.MAX_SEND_PER_RUN
SEND_INTERVAL_SEC = common.SEND_INTERVAL_SEC
NEAR_DUP_MIN_SHARED = common.NEAR_DUP_MIN_SHARED
NEAR_DUP_HOURS = common.NEAR_DUP_HOURS
NEAR_DUP_MAX = common.NEAR_DUP_MAX
PRESS_FETCH_MAX = common.PRESS_FETCH_MAX
PRESS_FETCH_TIMEOUT = common.PRESS_FETCH_TIMEOUT
PRESS_MAP = common.PRESS_MAP

KST = timezone(timedelta(hours=9))
STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "state", CONFIG_NAME + ".json"
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"

# 모든 키워드(평탄화) — 근접중복 토큰화 시 공통어 제외용
_ALL_KEYWORDS = [k for g in REQUIRE_GROUPS for k in g] + list(SEARCH_QUERIES)


# ---------- 매칭 ----------

def _contains_keyword(text, keyword):
    """키워드 매칭. 짧은 영문 키워드는 영문자 경계 적용."""
    if keyword in WORD_BOUNDARY_KEYWORDS:
        pattern = r"(?<![A-Za-z])" + re.escape(keyword) + r"(?![A-Za-z])"
        return re.search(pattern, text, re.IGNORECASE) is not None
    return keyword in text


def match_keyword(title, desc=""):
    """제목(+요약)이 모니터 조건을 만족하면 대표 키워드 반환, 아니면 None.

    조건: BLOCK 아님 + EXCLUDE 없음 + REQUIRE_GROUPS 각 그룹 1개 이상.
    """
    text = title + (" " + desc if (MATCH_IN_DESCRIPTION and desc) else "")
    if any(b in text for b in BLOCK_KEYWORDS):
        return None
    if any(_contains_keyword(text, x) for x in EXCLUDE_KEYWORDS):
        return None
    rep = None
    for group in REQUIRE_GROUPS:
        hit = next((k for k in group if _contains_keyword(text, k)), None)
        if hit is None:
            return None
        if rep is None:
            rep = hit
    return rep


# ---------- 유사 제목(near-duplicate) 판정 ----------

_STOP_TOKENS = frozenset({
    "속보", "단독", "공식", "종합", "기자", "뉴스", "오늘", "내일", "관련",
    "위해", "통해", "대한", "밝혀", "예정", "이번", "최대", "최초", "그룹",
    "추진", "전환", "조직",
})

_KW_LOWER = frozenset(k.lower() for k in _ALL_KEYWORDS)


def _title_tokens(title):
    t = re.sub(r"\[[^\]]*\]", " ", title)
    out = set()
    for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", t):
        if w in _STOP_TOKENS or w.lower() in _KW_LOWER or w.isdigit():
            continue
        out.add(w)
    return out


def _is_near_dup(tokens, sig_list):
    return any(len(tokens & s) >= NEAR_DUP_MIN_SHARED for s in sig_list)


def _load_recent_sigs(state, now):
    kept, sets = [], []
    for item in state.get("recent_sigs", []):
        try:
            ts = datetime.fromisoformat(item[0])
        except Exception:
            continue
        if (now - ts) <= timedelta(hours=NEAR_DUP_HOURS):
            kept.append(item)
            sets.append(set(item[1].split()))
    state["recent_sigs"] = kept[-NEAR_DUP_MAX:]
    return sets


# ---------- 수집 ----------

def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_tags(s):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def fetch_naver_api(query, count):
    """네이버 뉴스 검색 Open API. [(title, url, published_dt, source, desc), ...]"""
    url = (
        "https://openapi.naver.com/v1/search/news.json?query="
        + urllib.parse.quote(query)
        + "&display=%d&sort=date" % count
    )
    raw = _http_get(url, {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    })
    items = json.loads(raw).get("items", [])
    results = []
    for it in items:
        title = _strip_tags(it.get("title", ""))
        link = it.get("originallink") or it.get("link", "")
        desc = _strip_tags(it.get("description", ""))
        try:
            pub = parsedate_to_datetime(it.get("pubDate", "")).astimezone(KST)
        except Exception:
            pub = None
        results.append((title, link, pub, "", desc))
    return results


def fetch_google_rss(query, count):
    """Google News RSS fallback (네이버 키 없을 때)."""
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query + " when:1d")
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )
    raw = _http_get(url)
    results = []
    for m in re.finditer(r"<item>(.*?)</item>", raw, re.S):
        block = m.group(1)
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
        l = re.search(r"<link/?>(.*?)(?:</link>|<)", block, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        s = re.search(r"<source[^>]*>(.*?)</source>", block, re.S)
        dsc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.S)
        if not t or not l:
            continue
        title = _strip_tags(t.group(1))
        source = _strip_tags(s.group(1)) if s else ""
        desc = _strip_tags(dsc.group(1)) if dsc else ""
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]
        try:
            pub = parsedate_to_datetime(d.group(1)).astimezone(KST) if d else None
        except Exception:
            pub = None
        results.append((title, l.group(1).strip(), pub, source, desc))
    return results[:count]


def fetch_all(count):
    use_naver = bool(NAVER_ID and NAVER_SECRET)
    print("source: %s, queries: %d, count: %d"
          % ("naver-api" if use_naver else "google-rss", len(SEARCH_QUERIES), count))
    articles = []
    for q in SEARCH_QUERIES:
        try:
            articles += fetch_naver_api(q, count) if use_naver else fetch_google_rss(q, count)
        except Exception as e:
            print("fetch error (%s): %s" % (q, e))
    return articles


# ---------- 상태 ----------

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"seen_urls": [], "seen_titles": [], "recent_sigs": [],
                "last_run": "", "initialized": False}


def save_state(state):
    state["seen_urls"] = state.get("seen_urls", [])[-MAX_SEEN_URLS:]
    state["seen_titles"] = state.get("seen_titles", [])[-MAX_SEEN_URLS:]
    state["recent_sigs"] = state.get("recent_sigs", [])[-NEAR_DUP_MAX:]
    state["last_run"] = datetime.now(KST).isoformat()
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


_STRIP_PARAMS = frozenset({
    "fbclid", "gclid", "ref", "from", "sid", "cate", "stype", "page",
    "mode", "nt", "naver_source", "s_ref", "searchid", "search_id",
    "category", "section", "listid", "list_id",
})


def _norm_url(u):
    parts = urllib.parse.urlsplit(u)
    query = ""
    if parts.query:
        kept = [
            (k, v) for k, v in urllib.parse.parse_qsl(parts.query)
            if not k.lower().startswith("utm") and k.lower() not in _STRIP_PARAMS
        ]
        query = urllib.parse.urlencode(kept)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


# ---------- 발송 ----------

def _h(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _post_telegram(text):
    if DRY_RUN:
        print("[DRY_RUN] message:\n%s\n" % text)
        return
    chat_id_val = int(CHAT_ID) if CHAT_ID.lstrip("-").isdigit() else CHAT_ID
    payload = json.dumps({
        "chat_id": chat_id_val,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % BOT_TOKEN,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("telegram: %s" % resp.status)


def _host_of(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def _fetch_site_name(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=PRESS_FETCH_TIMEOUT) as resp:
            data = resp.read(65536)
    except Exception:
        return None
    # Auto-detect encoding: decode as UTF-8 first; if too many replacement
    # chars appear, fall back to CP949. Some outlets serve UTF-8 content but
    # wrongly declare charset=euc-kr in meta, so trusting the meta corrupts.
    text = data.decode("utf-8", errors="replace")
    if text.count(chr(0xFFFD)) > 2:
        try:
            text = data.decode("cp949")
        except Exception:
            pass
    m = re.search(
        r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', text, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name["\']', text, re.I
    )
    if not m:
        m = re.search(
            r'<meta[^>]+name=["\']copyright["\'][^>]+content=["\']([^"\']+)', text, re.I
        )
    if not m:
        return None
    name = html_mod.unescape(m.group(1)).strip().strip('.@ⓒ© ')
    name = name[:30]
    # Reject headline-like values (some sites put an article title in the
    # copyright/og meta): brackets or near-cap length signal a title.
    if not name or "[" in name or "]" in name or len(name) >= 30:
        return None
    return name


def press_name(url, source="", cache=None):
    if source:
        return source
    host = _host_of(url)
    for domain, name in PRESS_MAP.items():
        if host == domain or host.endswith("." + domain):
            return name
    if cache and host in cache and cache[host] != host:
        return cache[host]
    return None


def resolve_press_names(hits, cache):
    budget = PRESS_FETCH_MAX
    resolved = []
    for title, url, pub, source, kw, desc in hits:
        name = press_name(url, source, cache)
        if name is None:
            host = _host_of(url) or "기타"
            if budget > 0:
                budget -= 1
                name = _fetch_site_name(url) or host
                cache[host] = name
            else:
                name = host
        resolved.append((name, title, url, desc))
    return resolved


def blocked_url(url):
    host = _host_of(url)
    for d in BLOCK_DOMAINS:
        if host == d or host.endswith("." + d):
            return True
    return any(k in url.lower() for k in BLOCK_URL_KEYWORDS)


def allowed_press(url):
    if ALLOW_ALL_PRESS:
        return True
    host = _host_of(url)
    return any(host == d or host.endswith("." + d) for d in ALLOW_DOMAINS)


# ---------- 메인 ----------

def main():
    print("=== monitor: %s (%s) ===" % (NAME, CONFIG_NAME))
    if not DRY_RUN and (not BOT_TOKEN or not CHAT_ID):
        print("ERROR: TELEGRAM_BOT_TOKEN / chat_id 미설정")
        sys.exit(1)

    state = load_state()
    seen = set(state.get("seen_urls", []))
    seen_titles = set(state.get("seen_titles", []))
    now = datetime.now(KST)

    if not (ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR):
        print("outside active window %02d-%02d KST (now %02d시) — skip"
              % (ACTIVE_START_HOUR, ACTIVE_END_HOUR, now.hour))
        return

    last_run = None
    try:
        last_run = datetime.fromisoformat(state.get("last_run", ""))
    except (ValueError, TypeError):
        pass
    default_cutoff = now - timedelta(minutes=RECENCY_MINUTES)
    cutoff = min(last_run, default_cutoff) if last_run else default_cutoff
    window_start = now.replace(hour=ACTIVE_START_HOUR, minute=0, second=0, microsecond=0)
    if cutoff < window_start:
        cutoff = window_start

    night_mode = last_run is not None and (now - last_run) > timedelta(hours=2)
    night_range = None
    if night_mode:
        night_range = "%s ~ %s" % (window_start.strftime("%m-%d %H:%M"), now.strftime("%m-%d %H:%M"))

    articles = fetch_all(FETCH_COUNT_NIGHT if night_mode else FETCH_COUNT)
    print("fetched: %d, night_mode: %s" % (len(articles), night_mode))

    first_run = not state.get("initialized", False)
    recent_sigs = _load_recent_sigs(state, now)

    def _mark_seen(key, tkey):
        if key and key not in seen:
            seen.add(key)
            state.setdefault("seen_urls", []).append(key)
        if tkey not in seen_titles:
            seen_titles.add(tkey)
            state.setdefault("seen_titles", []).append(tkey)

    candidates = []
    for title, url, pub, source, desc in articles:
        key = _norm_url(url)
        tkey = re.sub(r"\s+", "", title)[:60]
        if (key and key in seen) or tkey in seen_titles:
            continue
        kw = match_keyword(title, desc)
        if (pub and pub < cutoff) or blocked_url(url) or not allowed_press(url) or not kw:
            _mark_seen(key, tkey)
            continue
        candidates.append((title, url, pub, source, kw, desc, key, tkey))

    accepted = []
    run_sigs = []
    for (title, url, pub, source, kw, desc, key, tkey) in candidates:
        toks = _title_tokens(title)
        if len(toks) >= NEAR_DUP_MIN_SHARED and (_is_near_dup(toks, recent_sigs) or _is_near_dup(toks, run_sigs)):
            _mark_seen(key, tkey)
            continue
        run_sigs.append(toks)
        accepted.append((title, url, pub, source, kw, desc, key, tkey, toks))

    print("hits: %d (candidates: %d)" % (len(accepted), len(candidates)))

    try:
        if first_run:
            print("first run — baseline only, no send")
            for item in accepted:
                _mark_seen(item[6], item[7])
        elif accepted:
            cache = state.setdefault("press_names", {})
            to_send = accepted[:MAX_SEND_PER_RUN]
            resolved = resolve_press_names(
                [(t, u, p, s, kw, d) for (t, u, p, s, kw, d, k, tk, to) in to_send], cache
            )
            if night_range:
                try:
                    _post_telegram("[%s] 오늘 뉴스 모아보기 %s" % (NAME, night_range))
                except Exception as e:
                    print("header send error: %s" % e)
            sent = 0
            for idx, (name, title, url, desc) in enumerate(resolved):
                key, tkey, toks = to_send[idx][6], to_send[idx][7], to_send[idx][8]
                excerpt = ("\n" + _h(desc[:200]) + ("..." if len(desc) > 200 else "")) if desc else ""
                try:
                    _post_telegram("<b>%s</b>\n<b><a href=\"%s\">%s</a></b>%s" % (_h(name), url, _h(title), excerpt))
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        print("429 rate limit — stop (%d sent)" % sent)
                        break
                    try:
                        _err_body = e.read().decode("utf-8", "replace")[:300]
                    except Exception:
                        _err_body = "<no body>"
                    print("send error 4xx (skip): %s | %s" % (e, _err_body))
                    _mark_seen(key, tkey)
                    continue
                except Exception as e:
                    print("send error — stop: %s" % e)
                    break
                _mark_seen(key, tkey)
                state.setdefault("recent_sigs", []).append([now.isoformat(), " ".join(toks)])
                recent_sigs.append(toks)
                sent += 1
                time.sleep(SEND_INTERVAL_SEC)
            print("sent: %d" % sent)
    finally:
        state["initialized"] = True
        save_state(state)


if __name__ == "__main__":
    main()
