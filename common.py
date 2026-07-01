# -*- coding: utf-8 -*-
"""SK 뉴스푸시 — 4개 모니터 공용 설정.

각 모니터(configs/*.py)는 이 파일의 값을 import 해서 쓰고,
키워드/상세키워드/chat_id 등 모니터별 항목만 따로 정의한다.
여기 값은 보통 손댈 필요 없다.
"""

# ── 매칭 범위 ────────────────────────────────────────────
# 제목만 볼지(False), 제목+요약(네이버 description)까지 볼지(True).
# 상세키워드는 본문 기반이라 요약까지 보는 편이 정확도가 높다.
MATCH_IN_DESCRIPTION = True

# ── 스포츠/게임 차단 (오너가家 동명이인·무관 기사 방지) ──────
BLOCK_KEYWORDS = [
    "야구", "KBO", "프로야구", "시범경기", "퓨처스",
    "홈런", "타자", "투수", "포수", "불펜", "타선", "타점", "타율",
    "삼진", "등판", "끝내기", "완봉", "완투", "이닝", "도루",
    "베어스", "자이언츠", "이글스", "히어로즈", "다이노스", "랜더스",
    "라이온즈", "타이거즈",
    "LCK", "롤드컵", "리그오브레전드", "롤스터", "젠지",
]

BLOCK_DOMAINS = [
    "mydaily.co.kr", "spotvnews.co.kr", "osen.co.kr", "xportsnews.com",
    "sportschosun.com", "starnewskorea.com", "mksports.co.kr",
    "sportsworldi.com", "sportsseoul.com", "isplus.com", "sportalkorea.com",
    "interfootball.co.kr", "stnsports.co.kr", "mhnse.com", "sportsq.co.kr",
    "gamefocus.co.kr", "maniareport.com", "stoo.com", "fomos.kr", "inven.co.kr",
]

BLOCK_URL_KEYWORDS = [
    "/sports/", "/baseball/", "/esports/", "/game/", "/lck/", "/kbo/",
    "/lol/", "sports.",
]

# ── 언론사 필터 ────────────────────────────────────────────
# 오너家·그룹 뉴스는 매체 폭이 넓어 전체 매체 허용. (스포츠/게임은 위에서 차단)
ALLOW_ALL_PRESS = True
ALLOW_DOMAINS = []   # ALLOW_ALL_PRESS=True 이면 무시됨

# ── 짧은 영문 키워드 경계 매칭 ──────────────────────────────
# "SK"를 단순 부분일치로 두면 RISK/TASK/DESK 등에 오탐. 영문 경계 적용.
# "SK텔레콤"(SK+한글)·"SK그룹"은 정상 매칭, "SKT"(SK+영문)는 비매칭.
WORD_BOUNDARY_KEYWORDS = {"SK", "SUPEX", "MYSUNI"}

# ── 시간대 / 수집 ─────────────────────────────────────────
# "실시간, 야간 알림 받지 않음" → 06~22시 발송, 야간은 아침에 모아보기.
ACTIVE_START_HOUR = 6
ACTIVE_END_HOUR = 22

RECENCY_MINUTES = 120
FETCH_COUNT = 30
FETCH_COUNT_NIGHT = 100
MAX_SEEN_URLS = 3000

# ── 발송 제어 (텔레그램 429 방지) ──────────────────────────
MAX_SEND_PER_RUN = 20
SEND_INTERVAL_SEC = 2.0

# ── 유사 기사(같은 보도자료) 묶음 차단 ─────────────────────
NEAR_DUP_MIN_SHARED = 2
NEAR_DUP_HOURS = 6
NEAR_DUP_MAX = 800

# ── 매체명 동적 조회 ───────────────────────────────────────
PRESS_FETCH_MAX = 10
PRESS_FETCH_TIMEOUT = 8

PRESS_MAP = {
    "segyebiz.com": "세계비즈",
    "ekn.kr": "에너지경제",
    "it.chosun.com": "IT조선", "biz.chosun.com": "조선비즈", "chosun.com": "조선일보",
    "joongang.co.kr": "중앙일보", "donga.com": "동아일보", "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문", "hankookilbo.com": "한국일보", "kmib.co.kr": "국민일보",
    "segye.com": "세계일보", "munhwa.com": "문화일보", "seoul.co.kr": "서울신문",
    "yna.co.kr": "연합뉴스", "news1.kr": "뉴스1", "newsis.com": "뉴시스",
    "mk.co.kr": "매일경제", "hankyung.com": "한국경제", "sedaily.com": "서울경제",
    "fnnews.com": "파이낸셜뉴스", "mt.co.kr": "머니투데이", "edaily.co.kr": "이데일리",
    "asiae.co.kr": "아시아경제", "heraldcorp.com": "헤럴드경제", "etnews.com": "전자신문",
    "zdnet.co.kr": "지디넷코리아", "ddaily.co.kr": "디지털데일리", "dt.co.kr": "디지털타임스",
    "inews24.com": "아이뉴스24", "bloter.net": "블로터", "ajunews.com": "아주경제",
    "etoday.co.kr": "이투데이", "businesspost.co.kr": "비즈니스포스트",
    "newspim.com": "뉴스핌", "dailian.co.kr": "데일리안", "ceoscoredaily.com": "CEO스코어데일리",
    "theguru.co.kr": "더구루", "kbs.co.kr": "KBS", "imbc.com": "MBC", "sbs.co.kr": "SBS",
    "jtbc.co.kr": "JTBC", "tvchosun.com": "TV조선", "ichannela.com": "채널A",
    "mbn.co.kr": "MBN", "ytn.co.kr": "YTN",
}
