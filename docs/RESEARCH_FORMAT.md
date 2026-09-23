# 리서치 입력 형식

`examples/research.json`은 2026-09-23 확인 자료와 합성 포트폴리오용 예시입니다. 실제 자동 실행에서는 매번 자료를 조사하여 `private/research.json`을 작성합니다. 필드는 `reporting/research_store.py`가 검증합니다.

| 필드 | 내용 |
|---|---|
| version | 정수 2 |
| as_of | 실제 조사한 한국 날짜 YYYY-MM-DD |
| sources | ID → {label, date, url}. HTTPS 원문, 발표일 또는 ‘확인일’ 표시 |
| stocks | research-brief의 security_id → 종목 분석 |
| portfolio | headline, summary, theme_codes, theme_label |
| sectors | 고정 sector_id → {label, outlook, watch, sources} |
| events | [{date 또는 null, title, watch, source, codes}] |

종목 분석에는 `sector, role, title, thesis, brief, base, up, down, watch, decision` 문자열과 `sources` ID 배열, `facts`, `financials`, `news`, `news_note`를 넣습니다. facts는 `{label, value, context}`이며 기간·확정 실적/회사 전망을 구분합니다. sources의 첫 원문은 brief의 실적 사실을 뒷받침해야 합니다.

financials는 `{kind, period, rows, analysis}` (kind는 company 또는 fund)입니다. rows 각 항목:

```json
{
  "id": "revenue",
  "label": "매출",
  "value": 1000,
  "previous": 800,
  "comparison": "YoY",
  "unit": "백만 USD",
  "period": "2026 Q2 · 2026-06-30 종료 3개월",
  "source": "company_q2"
}
```

위 숫자는 형식 예시입니다. value/previous는 유한 숫자 또는 null. 현재 값이 null이면 missing_reason 필수. 수치가 없으면 0을 넣지 않습니다. 전년 값은 같은 단위·기간 길이·회계 기준이어야 합니다. 비교를 확인하지 못하면 previous=null, comparison="미확인"으로 둡니다. 전년이 0/음수이면 성장률을 기계 계산하지 않습니다.

`revenue`, `operating_income`의 단위·기간이 같을 때만 영업이익률을 계산합니다. `operating_cash_flow`, `capex`의 단위·기간이 같을 때만 단순 잉여현금을 계산합니다. capex는 현금 유출의 **양수 절댓값**이며 어떤 설비/무형자산/리스 항목을 포함했는지 label과 analysis에 명시합니다. 회사 공시 FCF와 다르면 구분합니다. 다른 사업 특성의 지표는 별도 id를 사용할 수 있습니다.

뉴스는 `{date,title,summary,impact,source}`. summary는 사실, impact는 “분석:”으로 시작하는 조건부 해석입니다. 최근 7일 이내 뉴스만 메일에 노출됩니다. 빈 배열일 때 조사 범위와 미확인 사유를 news_note에 씁니다. 확인되지 않은 뉴스·일정을 생성하지 않습니다.

새 종목은 코드와 공식 자료를 먼저 확인합니다. 예시 파일에 없는 종목도 동일 형식으로 지원합니다. 주가 적정성·목표주가를 재무 성장률에서 임의 추론하지 않습니다. 알 수 없는 것은 구체적인 사유와 함께 미확인으로 둡니다.

## 종목 식별·조사 상태 (version 2)

`stocks`의 키는 `private/research-brief.json`에 있는 `security_id`를 그대로 사용합니다. 예: `US|UNKNOWN|MSFT|UNKNOWN`. 잔고 API만으로 거래소·상품 종류를 알 수 없으면 UNKNOWN으로 유지하고, **회사명으로 매칭하지 않습니다**. 조사 결과는 아래 identity에 별도로 넣습니다. 대소문자와 바깥 공백만 정규화하고, `BRK.B`/`BRK-B`, ADR/보통주, 클래스 A/B를 자동으로 합치지 않습니다.

검증 완료 종목에는 기존 필드와 함께 다음을 작성합니다. 아래 코드는 형식 예시이며 출처 ID는 실제 sources에 정의해야 합니다.

```json
{
  "status": "verified",
  "identity": {"market": "US", "exchange": "XNAS", "code": "MSFT", "product_type": "COMMON"},
  "identity_sources": ["company_filing"],
  "sector_id": "software",
  "sector": "소프트웨어·클라우드",
  "classification_basis": "공시에서 확인한 주요 사업을 근거로 분류",
  "classification_sources": ["company_filing"]
}
```

product_type은 COMMON / ADR / PREFERRED / ETF / ETN / FUND / OTHER. 거래소는 확인된 MIC 등 일관된 식별자를 사용합니다. 별칭이 꼭 필요하면 `code_alias: {from, to, sources}`에 정확한 코드와 확인 근거를 남깁니다. ETF·ETN·펀드는 `financials.kind="fund"`로 구성·보수·듀레이션 등 상품에 맞는 지표를 씁니다.

조사 전에는 `{ "status": "pending" }`으로 둘 수 있습니다. 확인 불가능한 경우 아래처럼 마무리합니다. **미확인은 조사를 생략하는 방법이 아닙니다.** 실제로 확인한 출처·확인일·구체적 사유가 필요합니다.

```json
{"status":"unresolved","reason":"공식 자료에서 해당 상품의 분류를 확인할 수 없음","checked_at":"실제 조사 날짜","sources":["checked_official_source"]}
```

고정 분류표는 `reporting/identity.py`의 `SECTORS`입니다. 업종과 label은 정확히 일치해야 하고 사용된 모든 sector_id에 sectors 분석·출처가 있어야 합니다. AI·고배당 같은 테마는 섹터가 아닙니다. 모든 보유가 verified여야 섹터 비중을 계산합니다. unresolved가 있으면 섹터 비중은 숨기되 사유를 명시한 최종 리포트는 허용합니다. pending이나 보유 종목 집합 불일치는 최종 메일을 차단합니다.

v1 파일은 연결 화면을 망가뜨리지 않도록 조사 대기로 표시하지만 최종 발송에는 사용하지 않습니다. 최신 실제 자료로 v2를 다시 작성하세요. 실제 계좌 경로에서는 examples 파일을 읽지 않습니다.
