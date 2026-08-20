# SEC EDGAR / GLEIF 실물 관찰 기록

실제 호출로 받은 응답에서 확인한 내용. DART 쪽은 `dart_quirks.redacted.md` 참조.

- EDGAR: 인증 불필요. **`User-Agent: <이름> <메일>` 헤더가 없으면 403.**
- GLEIF: 인증 불필요, 헤더도 불필요. 라이선스 **CC0**.

회사명·CIK·LEI·사업자번호 등 특정 기업을 가리키는 값은 형식만 남기고 가상값으로 바꿨다.
표본은 세 유형이다 — **US-A**: 대형 미국 상장사 / **KR-A**: 대형 국내 제조업 상장사 /
**KR-A-sub**: 그 계열 자회사.

---

## EDGAR

### E1. `filings.recent`이 행이 아니라 컬럼 지향 병렬 배열

```json
"recent": {
  "accessionNumber": ["0001234567-26-000101", "0001234567-26-000102", ...],
  "form":            ["4", "144", ...],
  "filingDate":      ["2026-08-13", "2026-08-11", ...]
}
```

레코드 배열이 아니다. 같은 인덱스끼리 묶어야 한 건이 된다. 길이가 어긋나면 조용히 밀린다.

### E2. `filings.files`에 나머지가 있다

`recent`는 최근 1,000건까지다. 그 이전은 `filings.files[]`가 가리키는 별도 JSON을
추가로 받아야 한다. `recent`만 보고 "이 회사 공시는 이게 전부"라고 하면 틀린다.

### E3. 결측이 빈 문자열

`act`, `fileNumber`, `filmNumber`, `items`, `reportDate`가 `null`이 아니라 `""`다.
DART와 같은 습관이지만 GLEIF는 `null`을 쓴다 — **세 소스의 결측 표현이 다르다.**

### E4. `companyconcept` / `companyfacts`는 태그 단위 시계열

```json
{"start":"2018-07-01","end":"2018-09-29","val":62900000000,
 "accn":"0001234567-18-000145","fy":2018,"fp":"FY","form":"10-K",
 "filed":"2018-11-05","frame":"CY2018Q3"}
```

- `val`은 **숫자**다. DART `thstrm_amount`는 콤마 낀 문자열. 파싱이 정반대다.
- 기간이 `start`/`end`. DART는 `'2025.01.01 ~ 2025.12.31'` 사람용 문자열.
- **같은 기간이 여러 번 나온다.** 최초 보고와 후속 정정(`accn`이 다름)이 모두 남는다.
  중복 제거 없이 합계를 내면 이중 계상된다.
- `frame`이 있는 항목과 없는 항목이 섞인다.

### E5. `companyfacts`는 크다

US-A 한 곳이 3.8MB, us-gaap 태그 **503개**. 회사 하나가 그 정도다.
커밋한 샘플은 태그 3개 × 5건으로 잘랐다(`_sample_note` 참조).

### E6. 매출 태그가 회사마다 다르다

`Revenues` / `RevenueFromContractWithCustomerExcludingAssessedTax` /
`SalesRevenueNet` 등. 한 태그로 전 회사를 훑을 수 없다.
DART의 `account_nm` 흔들림(`dart_quirks.redacted.md` ⑦)과 같은 문제가 태그 체계에서 반복된다.

### E7. 업종 코드가 `sic`다

DART는 KSIC(`induty_code`), EDGAR는 SIC. 체계가 다르고 1:1 대응이 아니다.
`sicDescription`이 같이 오지만 자유 텍스트다.

### E8. `formerNames`에 유효기간이 있다

```json
{"name": "EXAMPLE CORP", "from": "2007-01-10T05:00:00.000Z", "to": "2019-08-05T04:00:00.000Z"}
```

GLEIF `otherNames`는 언어·유형 태그를 쓰고 기간이 없다. **두 소스의 별칭 모델이 다르다.**

---

## GLEIF

### G1. `registeredAs`가 사업자등록번호다 — DART 조인 브릿지

```
GLEIF  registeredAs : "123-45-67890"
DART   bizr_no      : "1234567890"
```

**같은 값인데 하이픈 포맷이 다르다.** 정규화 없이 조인하면 0건이 나온다.
`registeredAt.id`(예: `RA000657`)가 어느 등록기관 번호인지 알려준다.
`creationDate`(1998-04-01)도 DART `est_dt`(19980401)와 맞물린다 — 보조 확인용.

### G2. 법인명이 현지어다

KR-A의 `legalName.name`은 **`가나전자(주)`(ko)**이고, 영문은
`otherNames[0]`에 `ALTERNATIVE_LANGUAGE_LEGAL_NAME`으로 들어 있다:

```
GLEIF  "GANA ELECTRONICS CO., LTD"
DART   "GANA ELECTRONICS CO,.LTD"     ← 원문의 오타
```

**영문명으로 조인하면 실패한다.** 자회사 목록에는 그리스어·헝가리어·중국어
법인명이 그대로 들어 있다(전각 괄호가 섞인 중국어 상호 등).

### G3. 이름 검색은 후보만 준다

대기업 그룹명으로 `filter[fulltext]` 검색 → **81건.** 전 세계 자회사가 이름만으로는
구분되지 않는다. 제재 명단 매칭을 이름으로 하면 안 되는 이유가 여기 있다.

### G4. 커버리지 구멍이 실재한다 — 상장사인데 LEI가 없다

코스닥 상장사 이름으로 `filter[fulltext]` 검색 → **0건.** 상장사인데 GLEIF에 없다.
LEI는 주로 금융거래 필요에 따라 발급되므로 전 기업을 덮지 않는다.
**세 소스를 다 조인해도 안 메워지는 회사가 있다**는 뜻이고, 이건 그대로 살려야 할 성질이다.

### G5. 관계 레코드에 **지분율이 없다**

```json
{"startNode":{"id":"1234500ABCDE6789XY02"},
 "endNode":  {"id":"1234500ABCDE6789XY01"},
 "type":"IS_DIRECTLY_CONSOLIDATED_BY","status":"ACTIVE",
 "periods":[{"startDate":"2012-04-03","type":"RELATIONSHIP_PERIOD"},
            {"startDate":"2025-01-01","endDate":"2025-06-30","type":"ACCOUNTING_PERIOD"}]}
```

`IS_DIRECTLY_CONSOLIDATED_BY` / `IS_ULTIMATELY_CONSOLIDATED_BY`는 **회계 연결 관계**이지
지분율이 아니다. `share_pct`를 쓰려면 DART 「최대주주 현황」에서 따로 가져오거나
우리가 추가한 필드임을 명시해야 한다.

`corroborationLevel`(`FULLY_` / `PARTIALLY_CORROBORATED`)이 근거 수준을 준다 —
우리 스키마의 `confidence` 컬럼과 같은 역할이라 여기서 빌려 쓸 수 있다.

### G6. 관계가 한 방향으로만 잡힌다

KR-A의 `direct-children`은 6건인데, 그중 한 해외 법인은 `direct-parent`가 **404**다.
자식 목록에 있는 법인과 이름이 비슷한 별개 법인인 것이고, 관계 보고 자체가 불완전하다.

**부모가 없는 최상위 법인도 404를 반환한다.** 404가 오류가 아니라 정상 응답이다.
`{"errors":[{"status":"404",...}]}` 형태라 `data` 키가 없다.

### G7. `INACTIVE`인데 만료 사유가 비어 있다

`entity.status=INACTIVE`가 **249,311건**인데, 표본을 보면
`expiration: {date: null, reason: null}`, `successorEntity: {lei: null, name: null}`이다.
소멸했다는 것만 알고 언제·왜·어디로 승계됐는지는 모른다.
해산 법인이 유령 엣지로 남는 문제가 이 모양 그대로다.

### G8. 코드값이 외부 코드체계다

`legalForm.id`(`5RCH`)는 ELF 코드, `region`(`KR-41`)은 ISO 3166-2,
`registeredAt.id`(`RA000657`)는 GLEIF 등록기관 목록. 전부 별도 조회가 필요하다.
`status`(엔티티)와 `registration.status`(등록)가 **다른 필드**다 —
`ACTIVE` / `ISSUED`처럼 값 집합도 다르다.
