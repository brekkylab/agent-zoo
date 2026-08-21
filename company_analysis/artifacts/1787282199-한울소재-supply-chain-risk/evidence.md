# 근거 대응표

| # | 주장 | 근거(파일/쿼리/필터) |
| --- | --- | --- |
| 1 | 한울소재 tier-1 공급사는 4곳(금하화학 CN 41.5%, 대진화학 KR 34.0%, 사쿠라가와화성 JP 12.0%, 성진정밀 KR 8.5%) | `data/supplychain/edges.csv`, `buyer_id=kr-hanul-materials` 필터. 쿼리 `workspace/.../queries/03_concentration.py` |
| 2 | tier-1 국가별 합계 CN 41.5% / KR 42.5% / JP 12.0%, HHI≈3358 | `queries/03_concentration.py` 출력 |
| 3 | 상류 8개 경로가 전부 cn-yuxi-mining(옥계광업집단, 리튬 정광) 한 곳으로 수렴 | `data/supplychain/edges.csv` 16·17행(`cn-beifang-lithium→cn-yuxi-mining`, `cn-beifeng-lithium→cn-yuxi-mining`), 재귀 전개 `queries/01_expand_tiers.py`, fan-in 확인 `queries/03_concentration.py` |
| 4 | 재귀 전개는 사이클 포함 11개 뿌리→말단 경로, 사이클은 대진화학↔성진정밀↔사쿠라가와화성 삼각형 | `queries/01_expand_tiers.py` 실행 결과, `workspace/.../tier_expansion.json` |
| 5 | 한울소재 상류에서 도달 가능한 회사는 총 7곳: 대진화학·성진정밀·사쿠라가와화성·금하화학(1차), 북방/북풍리튬재료(2차), 옥계광업집단(3차) | `queries/01_expand_tiers.py`, min_tier 출력 |
| 6 | cn-beifang-lithium이 MOCK-SDN "BEIFANG LITHIUM MATERIAL INDUSTRIAL CO"와 이름 유사도 0.91로 최고 일치 | `data/risk/sanctions.csv` 2행, `data/registry/gleif_lei.jsonl`(LEI 0000BEIFANGLI008GH09), `queries/02_sanctions_match.py` |
| 7 | cn-beifeng-lithium도 같은 제재 후보명과 유사도 0.87(별개 법인, 오탐 위험) | `data/risk/sanctions.csv` 2행, `data/registry/gleif_lei.jsonl`(LEI 0000BEIFENGLI009HJ09, 다른 주소: 江西省宜春市 vs 青海省西宁市), `queries/02_sanctions_match.py` |
| 8 | cn-tianyuan-holdings가 MOCK-SDN "TIANYUAN HOLDINGS LIMITED"와 유사도 0.87 | `data/risk/sanctions.csv` 3행, `queries/02_sanctions_match.py` |
| 9 | cn-tianyuan-holdings가 cn-yuxi-mining의 지분 68% 모회사이며, 옥계광업집단 자체는 제재 명단에 없음(간접 노출) | `data/registry/ownership.csv` 2행(note: "모회사가 제재 대상. 자회사 자체는 명단에 없다"), `data/registry/gleif_rr.jsonl` 1~2행(IS_DIRECTLY/ULTIMATELY_CONSOLIDATED_BY) |
| 10 | 나머지 제재 명단 4건(ORONTES, VOSTOK PRIBOR, KARAKUM METALS, PT SAMUDRA, NORTHERN LITHIUM)은 12개사와 유의미한 이름 일치 없음(임계값 0.55 이상 없음, 저유사도 노이즈 제외) | `queries/02_sanctions_match.py` 전체 출력 |
| 11 | 미국 고객사 us-northgate-cells가 한울소재 외 금하화학(리튬염 9.0%)·성진정밀(설비 6.0%)과도 직접 거래 | `data/supplychain/edges.csv` 2~4행 |
| 12 | 대진화학→북방리튬재료 거래는 `until=2025-11`, confidence=0.28로 낮음 | `data/supplychain/edges.csv` 13행 |
| 13 | 사쿠라가와화성 GLEIF 등록상태가 INACTIVE/LAPSED | `data/registry/gleif_lei.jsonl` 5번째 레코드 (`entity.status=INACTIVE`, `registration.status=LAPSED`) |
| 14 | 성진정밀은 한울소재 지분 30% 피투자사이며 LEI 없음(gleif_rr에 대응 레코드 없음) | `data/registry/ownership.csv` 3행 |
| 15 | 한울소재 2025 회계연도 연결(CFS) 매출 412,880,451,220원, 영업이익 34,118,772,005원 (별도 OFS 매출 298,114,903,776원) | `data/financials/dart_fnltt/99000101-2025.json`, `fs_div=CFS`/`OFS`, `sj_div=IS`, `account_nm=매출액/영업이익` 필터 |
| 16 | KSIC-SIC-NAICS 매핑이 1:1이 아님(예: 201 → SIC 2819, 2821 복수 대응) | `data/reference/industry_xwalk.csv` 3~4행 |
