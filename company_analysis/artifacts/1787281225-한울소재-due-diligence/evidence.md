# 근거 대응표

| # | 주장 | 근거(파일/쿼리) | 비고 |
|---|---|---|---|
| 1 | 한울소재 corp_code=99000101, LEI=0000HANULMAT00001A90 | `registry/company_index.csv` row2 | 조인 시작점 |
| 2 | DART bizr_no 9991001234 ↔ GLEIF registeredAs 999-10-01234 일치 | `registry/dart_company/99000101.json`, `registry/gleif_lei.jsonl` | 하이픈 제거 후 비교 |
| 3 | 상호/대표자/설립일/주소/업종 | `registry/dart_company/99000101.json` | 값 직접 인용 |
| 4 | stock_code=999101 (공백 아님) | `registry/dart_corpcode.xml` | 상장 종목코드 존재 |
| 5 | KSIC 20119 → SIC 2819 / NAICS 325180 | `reference/industry_xwalk.csv` | 기타 기초 무기화학물질 제조업 |
| 6 | 한울소재→한울캐피탈 51% 지분, 연결대상 | `registry/ownership.csv` row3 | filing-disclosed, as_of 2026-06-30 |
| 7 | 한울소재→성진정밀 30% 지분 | `registry/ownership.csv` row4 | GLEIF RR 대응 없음(성진정밀 LEI 미보유) |
| 8 | 한울캐피탈↔한울소재 GLEIF 연결관계(direct/ultimate consolidation) | `registry/gleif_rr.jsonl` line3-4 | ownership.csv 방향과 일치, 지분율은 없음 |
| 9 | 한울소재 본사, 제재명단 7건과 이름 유사도 대조 시 일치 후보 없음 | `risk/sanctions.csv` 전체 vs `dart_company/99000101.json`, `gleif_lei.jsonl` 상호/별칭, python difflib SequenceMatcher ratio>0.55 기준 무결과 | `queries/03-sanctions_match.py` |
| 10 | cn-beifang-lithium ↔ "BEIFANG LITHIUM MATERIAL INDUSTRIAL CO"(MOCK-SDN) 유사도 0.80~0.87 | `risk/sanctions.csv` row2, `registry/gleif_lei.jsonl` | 가능성 있는 일치 — 확인 필요 |
| 11 | cn-tianyuan-holdings ↔ "TIANYUAN HOLDINGS LIMITED"(MOCK-SDN) 유사도 0.89~0.91 | `risk/sanctions.csv` row3, `registry/gleif_lei.jsonl` | 가능성 있는 일치 — 확인 필요 |
| 12 | cn-tianyuan-holdings가 cn-yuxi-mining 지분 68% 보유 | `registry/ownership.csv` row2 | "모회사가 제재 대상, 자회사는 명단에 없음" 원문 note |
| 13 | 한울소재→cn-beifang-lithium 2단계 공급망 경로 존재(경로: 한울소재→대진화학/진허화공→beifang-lithium) | `supplychain/edges.csv`, 재귀 경로탐색 결과 | `queries/02-supplychain_tiers.py` |
| 14 | 한울소재→cn-yuxi-mining 3단계 공급망 경로 존재 | `supplychain/edges.csv`, 재귀 경로탐색 결과 | `queries/02-supplychain_tiers.py` |
| 15 | 한울소재 CFS FY2025 매출 4,128.8억/영업이익 341.2억/순이익 245.5억, 부채비율65.4%, 유동비율189.4% | `financials/dart_fnltt/99000101-2025.json` (fs_div=CFS) | `queries/04-financials.py` |
| 16 | 한울소재 OFS FY2025 매출 2,981.1억/영업이익 220.1억/순이익 158.8억, 부채비율69.6%, 유동비율176.8% | `financials/dart_fnltt/99000101-2025.json` (fs_div=OFS) | `queries/04-financials.py` |
| 17 | 한울캐피탈 CFS FY2025 자산 1조8,841억, 부채비율 862.9% | `financials/dart_fnltt/99000512-2025.json` (fs_div=CFS) | `queries/04-financials.py`; 금융업 계정(순이자손익 등) |
| 18 | 성진정밀 OFS FY2024(최신) 매출 410.1억, 부채비율111.0% | `financials/dart_fnltt/99000427-2024.json` (fs_div=OFS, 유일) | `queries/04-financials.py`; FY2025 데이터 없음(기준일 상이) |
| 19 | 한울소재 1차 공급/판매 관계 5건 | `supplychain/edges.csv` (buyer_id 또는 supplier_id == kr-hanul-materials 필터) | 직접 grep/필터 |
| 20 | 한울소재 공급망에 순환구조 존재(대진화학↔성진정밀↔사쿠라가와) | `supplychain/edges.csv` 재귀 확장, path 기반 방문가드 | `queries/02-supplychain_tiers.py` |
| 21 | watchlist.csv 6곳 중 5곳이 한울소재의 1~2차 관계사와 겹침 | `watchlist.csv` vs `supplychain/edges.csv`/`ownership.csv` 매칭 | 직접 대조 |
