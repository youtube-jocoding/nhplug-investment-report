# 리서치 입력 형식

`examples/research.json`은 2026-09-23 확인 자료와 합성 포트폴리오용 예시입니다. 실제 자동 실행에서는 매번 자료를 조사하여 `private/research.json`을 작성합니다. 필드는 `reporting/research_store.py`가 검증합니다.

| 필드 | 내용 |
|---|---|
| version | 정수 1 |
| as_of | 실제 조사한 한국 날짜 YYYY-MM-DD |
| sources | ID → {label, date, url}. HTTPS 원문, 발표일 또는 ‘확인일’ 표시 |
| stocks | 현재 보유 코드 → 종목 분석 |
| portfolio | headline, summary, theme_codes, theme_label |
| sectors | 사업 분류명 → {outlook, watch, sources} |
| events | [{date 또는 null, title, watch, source, codes}] |

종목 분석에는 `sector, role, title, thesis, brief, base, up, down, watch, decision` 문자열과 `sources` ID 배열, `facts`, `financials`, `news`, `news_note`를 넣습니다. facts는 `{label, value, context}`이며 기간·확정 실적/회사 전망을 구분합니다. sources의 첫 원문은 brief의 실적 사실을 뒷받침해야 합니다.

financials는 `{period, rows, analysis}`입니다. rows 각 항목:

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
