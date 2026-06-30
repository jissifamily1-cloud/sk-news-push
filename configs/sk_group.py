# -*- coding: utf-8 -*-
"""[T.ai] SK 그룹 뉴스 — SK/에스케이/수펙스추구협의회/SUPEX 기사.

(사용자 확정: 에스케이·수펙스추구협의회·SUPEX + SK 추가)
"""

NAME = "SK 그룹뉴스"
CHAT_ID = "-1003946546117"   # [T.ai] SK 그룹뉴스 (운영 슈퍼그룹·봇 관리자)  ※임시방=-1003965769876

SEARCH_QUERIES = ["SK", "에스케이", "수펙스추구협의회", "SUPEX"]

# = 넷 중 1개 이상 (단일 그룹 = 순수 OR). "SK"는 영문 경계 매칭(common.WORD_BOUNDARY_KEYWORDS).
REQUIRE_GROUPS = [
    ["SK", "에스케이", "수펙스추구협의회", "SUPEX"],
]

EXCLUDE_KEYWORDS = []
