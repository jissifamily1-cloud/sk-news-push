# SK 뉴스푸시 (4종 모니터)

네이버 뉴스에서 SK 관련 기사를 **키워드 + 상세키워드**로 잡아 텔레그램으로 푸시합니다.
공용 엔진 1개 + 모니터별 설정 4개 구조이며, GitHub Actions에서 10분마다 4종을 함께 돌립니다.

| # | 모니터 | config | 발송 조건 (제목+요약) | chat_id |
|---|--------|--------|----------------------|---------|
| 1 | SK 패밀리 | `sk_family` | (오너 일가 13인 中 1) **그리고** (SK·에스케이·SK그룹) | -5019814657 |
| 2 | SK 재단 | `sk_foundation` | (SK·에스케이·SK그룹·한국고등교육재단) **그리고** (행복나눔재단·최종현학술원·MYSUNI·포도뮤지엄·T&C재단·티엔씨재단), `SK온` 제외 | -5266207238 |
| 3 | SK 이슈 | `sk_issue` | (SK·에스케이·SK그룹) **그리고** (킨앤파트너스·가습기·그린워싱·공정위·압수수색), `B tv 뉴스` 제외 | -5195597641 |
| 4 | SK 그룹뉴스 | `sk_group` | 에스케이·수펙스추구협의회·SUPEX 中 1 | -5200480514 |

푸시 양식(머투 서비스와 동일):

```
연합뉴스
[기사 제목 (링크)]
기사 요약 한 줄...
```

---

## 폴더 구성

```
SK_뉴스푸시/
├── engine.py            # 공용 엔진 (수정 불필요)
├── common.py            # 공용 설정 (차단어·시간대·매체명 등)
├── configs/
│   ├── sk_family.py     # ← 모니터별 키워드/상세키워드/chat_id
│   ├── sk_foundation.py
│   ├── sk_issue.py
│   └── sk_group.py
├── state/               # 모니터별 중복방지 상태 (자동 관리)
├── .github/workflows/monitor.yml   # 10분 cron · 4종 matrix
├── SECRETS.md           # 키 메모 (.gitignore, 커밋 안 됨)
└── .gitignore
```

매칭 규칙: `REQUIRE_GROUPS`의 **각 그룹에서 1개 이상** 포함(그룹 간 AND, 그룹 내 OR) + `EXCLUDE_KEYWORDS` 없음.
키워드만 바꾸려면 `configs/*.py`만 손대면 됩니다.

---

## 셋업 (최초 실페미 1홨)

1. 이 폴더를 GitHub 저장소로 push (public 권장 → Actions 무료 무제한)
2. **Secrets 3개 등록** (`SECRETS.md` 참고): `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`
3. **새 볷 을 각 방에 초대** (채널이면 봇을 관리자로) → 안 그묔면 발송 안 됨
4. Actions 탭에서 `sk-news-push` **Run workflow**룜 즉시 테스트
   - 최초 실행혘 발송하지 않고 baseline만 잡습니다(과로 기사 폭주 방지). 2회차부터 신규 발송.

### 됌스트방 먼저 검증하려면
워크플로 `env`에 `TELEGRAM_CHAT_ID: 테스트방의 id>`를 추가하면 4종 모두 테스트방으로 보낵니다.
검증을 뀈 그 줄을 지우면 각 config의 운영 chat_id로 돌아갑니다.

---

## 로컬 테스트 (발송 없이)

```bash
export NAVER_CLIENT_ID=...  NAVER_CLIENT_SECRET=...
CONFIG=sk_issue DRY_RUN=1 python engine.py     # 보내 면시지를 콘솔에만 출력
```

`CONFIG`에 `sk_family` / `sk_foundation` / `sk_issue` / `sk_group` 중 하나를 넣어 모니터별룜 확인.

---

## 비용 / 한도

- **GitHub Actions**: public 저장소면 무제한 무료.
- **네이버 API**: 앱당 하룬 25,000회. 4종 합칠 질의 약 30개 × 10분 간격 × 16시간 ≈ 하�= 3천 회 안쪽— 여유.
- **텔레그램**: 발송 간격 2초·건당 20건 상한 내장.
