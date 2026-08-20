"""픽스처 — 손으로 쓴 합성 12사.

생성기가 아니다. 모든 값이 이 파일에 literal로 박혀 있고, `emit.py`가 이걸
`company_analysis/data/` 아래 원천별 스키마로 펼쳐 쓴다.

스키마는 `datagen/reference/`의 실제 응답을 따른다. 값은 전부 가공이되
모양·타입·코드체계·버릇(`dart_quirks.md`, `edgar_gleif_quirks.md`)은 실물 그대로다.

실존 충돌 방지: corp_code는 `99` 접두(실물은 00~01), CIK는 10자리 99억대,
LEI는 LOU 접두 `0000`(미할당), 사업자번호는 `999` 접두.
"""

AS_OF = "2026-06-30"
FREEZE_YEAR = 2025          # 최신 사업연도
CURRENT_TERM = 57           # 한울소재 기수 기준

# ---------------------------------------------------------------- LEI 체크섬
def lei(base18: str) -> str:
    """ISO 17442 mod 97-10 체크디짓을 붙여 20자리 LEI를 만든다."""
    assert len(base18) == 18, base18
    n = int("".join(str(int(c, 36)) for c in (base18 + "00")))
    return base18 + f"{98 - n % 97:02d}"


def houjin_bango_check(base12: str) -> int:
    """일본 法人番号 검사용 숫자. 오른쪽부터 홀수 자리 ×1, 짝수 자리 ×2."""
    s = sum(int(d) * (1 if i % 2 == 0 else 2) for i, d in enumerate(reversed(base12)))
    return 9 - (s % 9)


# ---------------------------------------------------------------- 12사
# role: 리포트에는 안 나가는 우리 메모. eval/ground_truth.yaml과 짝을 이룬다.
COMPANIES = [
    dict(
        company_id="kr-hanul-materials", country="KR", primary_source="dart",
        role="분석 기준사. 2차전지 양극재 소재. KOSDAQ 상장",
        corp_code="99000101", cik=None, lei_base="0000HANULMAT00001A",
        # DART company.json — 전 필드 STRING, 결측은 ''
        dart=dict(
            corp_name="한울소재(주)", corp_name_eng="HANUL MATERIALS CO., LTD",
            stock_name="한울소재", stock_code="999101", ceo_nm="정하윤, 오세진",
            corp_cls="K", jurir_no="1101119900101", bizr_no="9991001234",
            adres="충청북도 청주시 흥덕구 대신로 187 (강서동)",
            hm_url="www.hanul-materials.example", ir_url="", phn_no="043-260-1100",
            fax_no="043-260-1109", induty_code="20119", est_dt="20040611", acc_mt="12",
        ),
        corpcode_name="한울소재",
        gleif=dict(name_ko="한울소재(주)", name_en="HANUL MATERIALS CO.,LTD",
                   city="Cheongju", region="KR-43", postal="28454",
                   addr_ko="충청북도 청주시 흥덕구 대신로 187 (강서동)",
                   addr_en="187, Daesin-ro, Heungdeok-gu, Cheongju-si, Chungcheongbuk-do",
                   registered_as="999-10-01234", ra_id="RA000657",
                   legal_form="5RCH", status="ACTIVE", created="2004-06-11",
                   initial_reg="2018-03-14", last_update="2026-04-22"),
        fin_profile="manufacturing", fin_years=[2025],
    ),
    dict(
        company_id="kr-daejin-chem", country="KR", primary_source="dart",
        role="1차 협력사. 전해액 첨가제. 적자 기업 — 음수 금액 표본",
        corp_code="99000204", cik=None, lei_base="0000DAEJINCHM0002B",
        dart=dict(
            corp_name="(주)대진화학", corp_name_eng="DAEJIN CHEMICAL CO.,LTD",
            stock_name="대진화학", stock_code="", ceo_nm="박선우",
            corp_cls="E", jurir_no="1101119900204", bizr_no="9992005678",
            adres="울산광역시 남구 여천로 332",
            hm_url="www.daejin-chem.example", ir_url="", phn_no="052-277-3400",
            fax_no="052-277-3409", induty_code="201", est_dt="19970218", acc_mt="12",
        ),
        corpcode_name="대진화학",
        gleif=dict(name_ko="(주)대진화학", name_en="DAEJIN CHEMICAL CO., LTD",
                   city="Ulsan", region="KR-31", postal="44776",
                   addr_ko="울산광역시 남구 여천로 332",
                   addr_en="332, Yeocheon-ro, Nam-gu, Ulsan",
                   registered_as="999-20-05678", ra_id="RA000657",
                   legal_form="5RCH", status="ACTIVE", created="1997-02-18",
                   initial_reg="2019-06-03", last_update="2026-01-19"),
        fin_profile="manufacturing_loss", fin_years=[2025],
    ),
    dict(
        company_id="kr-daejin-chem-cosmetic", country="KR", primary_source="dart",
        role="동명이인 함정. 상호가 (주)대진화학으로 같으나 화장품 제조, 무관",
        corp_code="99000318", cik=None, lei_base="0000DAEJINCOS0003C",
        dart=dict(
            corp_name="(주)대진화학", corp_name_eng="DAEJIN CHEMICAL CO., LTD.",
            stock_name="대진화학", stock_code="", ceo_nm="한지수",
            corp_cls="E", jurir_no="1101119900318", bizr_no="9993009012",
            adres="경기도 화성시 향남읍 발안공단로 55",
            hm_url="", ir_url="", phn_no="031-353-7700",
            fax_no="", induty_code="20431", est_dt="20120905", acc_mt="12",
        ),
        corpcode_name="대진화학",
        gleif=dict(name_ko="(주)대진화학", name_en="DAEJIN CHEMICAL CO., LTD.",
                   city="Hwaseong", region="KR-41", postal="18622",
                   addr_ko="경기도 화성시 향남읍 발안공단로 55",
                   addr_en="55, Baran-gongdan-ro, Hyangnam-eup, Hwaseong-si, Gyeonggi-do",
                   registered_as="999-30-09012", ra_id="RA000657",
                   legal_form="5RCH", status="ACTIVE", created="2012-09-05",
                   initial_reg="2021-11-08", last_update="2025-12-02"),
        fin_profile="manufacturing_small", fin_years=[2025],
    ),
    dict(
        company_id="kr-sungjin-precision", country="KR", primary_source="dart",
        role="1차 협력사이자 한울소재 지분 30% 피출자사. LEI 없음 + FY2025 재무 결측",
        corp_code="99000427", cik=None, lei_base=None,          # ← LEI 없음
        dart=dict(
            corp_name="주식회사 성진정밀", corp_name_eng="SUNGJIN PRECISION INC",
            stock_name="성진정밀", stock_code="", ceo_nm="최도현",
            corp_cls="E", jurir_no="1101119900427", bizr_no="9994003456",
            adres="경상남도 김해시 골든루트로 88번길 21",
            hm_url="www.sungjin-precision.example", ir_url="", phn_no="055-320-6600",
            fax_no="055-320-6609", induty_code="29199", est_dt="20081103", acc_mt="12",
        ),
        corpcode_name="성진정밀",
        gleif=None,                                              # ← GLEIF 미등재
        fin_profile="manufacturing_small", fin_years=[2024],     # ← FY2025 없음
    ),
    dict(
        company_id="kr-hanul-capital", country="KR", primary_source="dart",
        role="한울소재 51% 자회사. 여신전문금융업 — 계정 체계가 제조업과 다름",
        corp_code="99000512", cik=None, lei_base="0000HANULCAP0005DA",
        dart=dict(
            corp_name="한울캐피탈(주)", corp_name_eng="HANUL CAPITAL CO., LTD",
            stock_name="한울캐피탈", stock_code="", ceo_nm="서정민",
            corp_cls="E", jurir_no="1101119900512", bizr_no="9995007890",
            adres="서울특별시 영등포구 국제금융로 10 (여의도동)",
            hm_url="www.hanul-capital.example", ir_url="www.hanul-capital.example/ir",
            phn_no="02-3775-2200", fax_no="02-3775-2209",
            induty_code="64992", est_dt="20140317", acc_mt="12",
        ),
        corpcode_name="한울캐피탈",
        gleif=dict(name_ko="한울캐피탈(주)", name_en="HANUL CAPITAL CO., LTD",
                   city="Seoul", region="KR-11", postal="07326",
                   addr_ko="서울특별시 영등포구 국제금융로 10 (여의도동)",
                   addr_en="10, Gukjegeumyung-ro, Yeongdeungpo-gu, Seoul",
                   registered_as="999-50-07890", ra_id="RA000657",
                   legal_form="5RCH", status="ACTIVE", created="2014-03-17",
                   initial_reg="2017-09-27", last_update="2026-05-11"),
        fin_profile="financial", fin_years=[2025],
    ),
    dict(
        company_id="jp-sakuragawa-kasei", country="JP", primary_source="gleif",
        role="1차 협력사. GLEIF상 INACTIVE(소멸)인데 공급망 엣지는 살아 있음 — 유령 엣지",
        corp_code=None, cik=None, lei_base="0000SAKURAGAWA006E",
        dart=None, corpcode_name=None,
        gleif=dict(name_ko="桜川化成株式会社", name_en="Sakuragawa Kasei Co., Ltd.",
                   lang="ja", city="Yokkaichi", region="JP-24", postal="510-0851",
                   addr_ko="三重県四日市市塩浜町3-12",
                   addr_en="3-12 Shiohama-cho, Yokkaichi-shi, Mie",
                   registered_as="9190001008833", ra_id="RA000472",
                   legal_form="A0LC", status="INACTIVE", created="1974-05-20",
                   initial_reg="2016-02-11", last_update="2026-02-28"),
        fin_profile=None, fin_years=[],
    ),
    dict(
        company_id="cn-jinhe-chem", country="CN", primary_source="gleif",
        role="1차 협력사. 중국 리튬염. 제재 대상 2차 협력사를 끼고 있음",
        corp_code=None, cik=None, lei_base="0000JINHECHEM007FG",
        dart=None, corpcode_name=None,
        gleif=dict(name_ko="金河化学工业有限公司", name_en="Jinhe Chemical Industrial Co., Ltd.",
                   lang="zh", city="Ningde", region="CN-35", postal="352100",
                   addr_ko="福建省宁德市蕉城区金涵路68号",
                   addr_en="No.68 Jinhan Road, Jiaocheng District, Ningde, Fujian",
                   registered_as="91350900MA2XKN4H7L", ra_id="RA000544",
                   legal_form="LSCV", status="ACTIVE", created="2011-07-14",
                   initial_reg="2018-08-30", last_update="2026-03-17"),
        fin_profile=None, fin_years=[],
    ),
    dict(
        company_id="cn-beifang-lithium", country="CN", primary_source="gleif",
        role="2차 협력사. 제재 대상 — 명단 표기와 상호가 어긋나 별칭을 거쳐야 이어짐",
        corp_code=None, cik=None, lei_base="0000BEIFANGLI008GH",
        dart=None, corpcode_name=None,
        gleif=dict(name_ko="北方锂业材料有限公司", name_en="Beifang Lithium Materials Co., Ltd.",
                   lang="zh", city="Xining", region="CN-63", postal="810007",
                   addr_ko="青海省西宁市城东区互助路215号",
                   addr_en="No.215 Huzhu Road, Chengdong District, Xining, Qinghai",
                   registered_as="91630100MA75RP2X3C", ra_id="RA000544",
                   legal_form="LSCV", status="ACTIVE", created="2016-03-22",
                   initial_reg="2019-04-02", last_update="2025-11-26"),
        fin_profile=None, fin_years=[],
    ),
    dict(
        company_id="cn-beifeng-lithium", country="CN", primary_source="gleif",
        role="유사명 미끼. Beifang과 영문 상호가 한 글자(a/e)만 다르나 별개 법인이고 제재 대상이 아님",
        corp_code=None, cik=None, lei_base="0000BEIFENGLI009HJ",
        dart=None, corpcode_name=None,
        gleif=dict(name_ko="北风锂业材料有限公司", name_en="Beifeng Lithium Materials Co., Ltd.",
                   lang="zh", city="Yichun", region="CN-36", postal="336000",
                   addr_ko="江西省宜春市袁州区明月北路1号",
                   addr_en="No.1 Mingyue North Road, Yuanzhou District, Yichun, Jiangxi",
                   registered_as="91360900MA38T4W62N", ra_id="RA000544",
                   legal_form="LSCV", status="ACTIVE", created="2018-01-09",
                   initial_reg="2020-10-15", last_update="2026-06-04"),
        fin_profile=None, fin_years=[],
    ),
    dict(
        company_id="cn-yuxi-mining", country="CN", primary_source="gleif",
        role="3차 협력사. 자체는 깨끗하나 지분 68% 모회사가 제재 대상 — 간접 노출",
        corp_code=None, cik=None, lei_base="0000YUXIMINING10JK",
        dart=None, corpcode_name=None,
        gleif=dict(name_ko="玉溪矿业集团有限公司", name_en="Yuxi Mining Group Co., Ltd.",
                   lang="zh", city="Yuxi", region="CN-53", postal="653100",
                   addr_ko="云南省玉溪市红塔区凤凰路156号",
                   addr_en="No.156 Fenghuang Road, Hongta District, Yuxi, Yunnan",
                   registered_as="91530400MA6K8P9R1D", ra_id="RA000544",
                   legal_form="LSCV", status="ACTIVE", created="2009-11-30",
                   initial_reg="2017-12-21", last_update="2026-01-08"),
        fin_profile=None, fin_years=[],
    ),
    dict(
        company_id="cn-tianyuan-holdings", country="CN", primary_source="gleif",
        role="제재 대상 지주사. 玉溪矿业 지분 68% 보유 — 3차의 간접 노출 경로",
        corp_code=None, cik=None, lei_base="0000TIANYUANH11KLA",
        dart=None, corpcode_name=None,
        gleif=dict(name_ko="天源控股有限公司", name_en="Tianyuan Holdings Ltd.",
                   lang="zh", city="Kunming", region="CN-53", postal="650000",
                   addr_ko="云南省昆明市五华区东风西路88号",
                   addr_en="No.88 Dongfeng West Road, Wuhua District, Kunming, Yunnan",
                   registered_as="91530100MA6DE7N40Q", ra_id="RA000544",
                   legal_form="LSCV", status="ACTIVE", created="2005-06-17",
                   initial_reg="2017-05-09", last_update="2026-02-13"),
        fin_profile=None, fin_years=[],
    ),
    dict(
        company_id="us-northgate-cells", country="US", primary_source="edgar",
        role="한울소재의 최종 고객. EDGAR 레코드 표본",
        corp_code=None, cik="9900000101", lei_base="0000NORTHGATE12LMA",
        dart=None, corpcode_name=None,
        edgar=dict(name="NORTHGATE CELLS, INC.", sic="3691",
                   sic_desc="Storage Batteries", ein="990123456",
                   tickers=["NGCL"], exchanges=["Nasdaq"],
                   state_inc="DE", fiscal_year_end="1231",
                   street1="4400 INDUSTRIAL PKWY", city="RENO",
                   state="NV", zipcode="89506",
                   former_names=[dict(name="NORTHGATE ENERGY STORAGE INC",
                                      **{"from": "2016-02-01T05:00:00.000Z",
                                         "to": "2021-06-14T04:00:00.000Z"})]),
        gleif=dict(name_ko="NORTHGATE CELLS, INC.", name_en="NORTHGATE CELLS, INC.",
                   lang="en", city="Reno", region="US-NV", postal="89506",
                   addr_ko="4400 Industrial Pkwy", addr_en="4400 Industrial Pkwy",
                   registered_as="99-0123456", ra_id="RA000602",
                   legal_form="XTIQ", status="ACTIVE", created="2016-02-01",
                   initial_reg="2017-03-08", last_update="2026-05-29"),
        fin_profile="edgar", fin_years=[2023, 2024, 2025],
    ),
]

for c in COMPANIES:
    c["lei"] = lei(c["lei_base"]) if c.get("lei_base") else None


# ---------------------------------------------------------------- 재무
# DART fnltt는 한 응답에 CFS와 OFS가 섞여 오고(dart_quirks ③),
# `당기순이익(손실)`이 ord 29/61에 중복 등장한다(④). ord는 실물 표본 그대로.
#
# 값은 원 단위 정수. 방출 시 콤마 문자열로 포맷하고 음수는 '-' 접두(⑤).
# (계정명, sj_div, ord_cfs, ord_ofs)
MANUFACTURING_LAYOUT = [
    ("유동자산",           "BS",  1,  2),
    ("비유동자산",          "BS",  3,  4),
    ("자산총계",           "BS",  5,  6),
    ("유동부채",           "BS",  7,  8),
    ("비유동부채",          "BS",  9, 10),
    ("부채총계",           "BS", 11, 12),
    ("자본금",             "BS", 13, 15),
    ("이익잉여금",          "BS", 17, 19),
    ("자본총계",           "BS", 21, 22),
    ("매출액",             "IS", 23, 24),
    ("영업이익",           "IS", 25, 26),
    ("법인세차감전 순이익",   "IS", 27, 28),
    ("당기순이익(손실)",     "IS", 29, 30),
    ("당기순이익(손실)",     "IS", 61, 62),   # ← 의도된 중복. 실물이 그렇다
    ("총포괄손익",          "IS", 63, 64),
]

# 금융업은 계정 체계가 통째로 다르다 — 매출액·영업이익이 없다(dart_quirks ⑦).
FINANCIAL_LAYOUT = [
    ("자산총계",           "BS",  1,  2),
    ("부채총계",           "BS",  3,  4),
    ("자본금",             "BS",  5,  6),
    ("이익잉여금",          "BS",  7,  8),
    ("자본총계",           "BS",  9, 10),
    ("예수부채",           "BS", 11, 12),
    ("당기손익-공정가치측정금융자산", "BS", 13, 14),
    ("파생상품자산",         "BS", 15, 16),
    ("파생상품부채",         "BS", 17, 18),
    ("순이자손익",          "IS", 31, 32),
    ("이자수익",           "IS", 33, 34),
    ("이자비용",           "IS", 35, 36),
    ("순수수료손익",         "IS", 37, 38),
    ("영업이익(손실)",       "IS", 39, 40),   # ← '영업이익'이 아니다
    ("법인세차감전 순이익",   "IS", 41, 42),
    ("당기순이익(손실)",     "IS", 43, 44),
    ("총포괄손익",          "IS", 45, 46),
]

# {company_id: {bsns_year: {"cfs": {계정: [당기, 전기, 전전기]}, "ofs": {...}}}}
# 억 단위로 읽히도록 원 단위 정수. 연결 > 별도인 정상 구조.
FINANCIALS = {
    "kr-hanul-materials": {2025: dict(term=57, layout="manufacturing", cfs={
        "유동자산":        [186_402_551_330, 171_884_209_005, 148_330_772_411],
        "비유동자산":       [243_775_110_884, 228_004_918_772, 199_411_650_338],
        "자산총계":        [430_177_662_214, 399_889_127_777, 347_742_422_749],
        "유동부채":        [ 98_441_320_775,  91_003_882_140,  84_772_119_806],
        "비유동부채":       [ 71_620_884_003,  69_115_447_218,  61_338_920_557],
        "부채총계":        [170_062_204_778, 160_119_329_358, 146_111_040_363],
        "자본금":          [ 12_400_000_000,  12_400_000_000,  11_800_000_000],
        "이익잉여금":       [188_775_119_446, 168_224_880_115, 138_990_115_772],
        "자본총계":        [260_115_457_436, 239_769_798_419, 201_631_382_386],
        "매출액":          [412_880_451_220, 371_552_009_884, 318_770_115_402],
        "영업이익":        [ 34_118_772_005,  30_442_119_887,  21_009_338_776],
        "법인세차감전 순이익": [ 31_886_005_412,  28_770_119_003,  19_442_887_115],
        "당기순이익(손실)":  [ 24_550_338_771,  22_114_880_006,  15_337_009_442],
        "총포괄손익":       [ 25_881_447_119,  23_009_772_884,  16_112_338_005],
    }, ofs={
        "유동자산":        [131_009_884_772, 120_338_115_446, 104_772_009_331],
        "비유동자산":       [178_442_330_115, 167_881_004_772, 148_119_557_880],
        "자산총계":        [309_452_214_887, 288_219_120_218, 252_891_567_211],
        "유동부채":        [ 74_118_009_442,  68_552_331_770,  63_009_884_115],
        "비유동부채":       [ 52_880_447_331,  51_119_772_004,  45_338_115_886],
        "부채총계":        [126_998_456_773, 119_672_103_774, 108_348_000_001],
        "자본금":          [ 12_400_000_000,  12_400_000_000,  11_800_000_000],
        "이익잉여금":       [138_442_119_886, 124_009_331_772, 102_557_880_445],
        "자본총계":        [182_453_758_114, 168_547_016_444, 144_543_568_210],
        "매출액":          [298_114_903_776, 268_880_119_442, 231_009_557_884],
        "영업이익":        [ 22_009_884_331,  19_775_331_006,  13_442_119_770],
        "법인세차감전 순이익": [ 20_338_772_115,  18_119_009_884,  12_557_446_003],
        "당기순이익(손실)":  [ 15_881_119_004,  14_009_447_772,   9_772_338_115],
        "총포괄손익":       [ 16_442_005_886,  14_557_880_331,  10_119_772_446],
    })},
    # 적자 기업 — 음수 표본(dart_quirks ⑤). 연결/별도 동일 값(자회사 없음)
    "kr-daejin-chem": {2025: dict(term=29, layout="manufacturing", cfs={
        "유동자산":        [ 31_442_009_885,  38_119_772_004,  44_557_331_886],
        "비유동자산":       [ 52_880_115_447,  56_009_338_772,  58_772_446_119],
        "자산총계":        [ 84_322_125_332,  94_129_110_776, 103_329_778_005],
        "유동부채":        [ 58_119_884_772,  55_442_331_009,  49_009_772_115],
        "비유동부채":       [ 41_557_009_446,  38_880_119_331,  33_119_447_884],
        "부채총계":        [ 99_676_894_218,  94_322_450_340,  82_129_219_999],
        "자본금":          [  8_500_000_000,   8_500_000_000,   8_500_000_000],
        "이익잉여금":       [-35_880_412_006, -23_442_119_884, -10_119_772_331],
        "자본총계":        [-15_354_768_886,   -193_339_564,  21_200_558_006],
        "매출액":          [ 88_204_113_905,  95_119_772_446, 101_338_009_557],
        "영업이익":        [-12_447_908_331,  -9_880_119_772,  -4_119_446_005],
        "법인세차감전 순이익": [-13_119_884_772, -10_442_331_009,  -4_772_115_886],
        "당기순이익(손실)":  [-12_438_292_122, -13_322_347_553,  -4_557_009_331],
        "총포괄손익":       [-12_772_446_119, -13_557_880_004,  -4_880_331_772],
    }, ofs=None)},   # ofs=None → 별도만 없는 회사. 응답에 CFS 15행만 온다
    "kr-daejin-chem-cosmetic": {2025: dict(term=14, layout="manufacturing", cfs=None, ofs={
        "유동자산":        [  4_118_772_005,   3_880_119_446,   3_442_009_331],
        "비유동자산":       [  6_557_331_884,   6_119_446_772,   5_772_115_009],
        "자산총계":        [ 10_676_103_889,   9_999_566_218,   9_214_124_340],
        "유동부채":        [  2_880_009_447,   2_557_119_884,   2_119_772_005],
        "비유동부채":       [  1_442_115_331,   1_338_446_009,   1_009_884_772],
        "부채총계":        [  4_322_124_778,   3_895_565_893,   3_129_656_777],
        "자본금":          [  1_000_000_000,   1_000_000_000,   1_000_000_000],
        "이익잉여금":       [  4_553_979_111,   4_304_000_325,   4_284_467_563],
        "자본총계":        [  6_353_979_111,   6_104_000_325,   6_084_467_563],
        "매출액":          [  9_120_447_300,   8_557_119_884,   8_119_772_446],
        "영업이익":        [    442_115_886,     338_009_772,     309_446_115],
        "법인세차감전 순이익": [    331_772_009,     255_884_446,     231_119_005],
        "당기순이익(손실)":  [    249_978_786,     195_532_762,     174_337_009],
        "총포괄손익":       [    251_119_446,     196_772_005,     175_009_884],
    })},
    # FY2025 없음 — FY2024가 최신(dart_quirks ⑪). 추세 외삽 금지 케이스
    "kr-sungjin-precision": {2024: dict(term=17, layout="manufacturing", cfs=None, ofs={
        "유동자산":        [ 22_880_119_446,  20_557_331_009,  18_119_772_884],
        "비유동자산":       [ 35_442_009_115,  33_772_446_886,  31_009_884_331],
        "자산총계":        [ 58_322_128_561,  54_329_777_895,  49_129_657_215],
        "유동부채":        [ 18_119_884_772,  17_009_331_446,  15_442_115_009],
        "비유동부채":       [ 12_557_446_005,  12_119_772_884,  11_880_009_331],
        "부채총계":        [ 30_677_330_777,  29_129_104_330,  27_322_124_340],
        "자본금":          [  3_200_000_000,   3_200_000_000,   3_200_000_000],
        "이익잉여금":       [ 21_444_797_784,  19_000_673_565,  15_607_532_875],
        "자본총계":        [ 27_644_797_784,  25_200_673_565,  21_807_532_875],
        "매출액":          [ 41_009_772_446,  38_442_115_884,  34_119_009_331],
        "영업이익":        [  3_880_115_009,   3_557_446_772,   2_772_331_886],
        "법인세차감전 순이익": [  3_442_009_884,   3_119_772_115,   2_557_446_009],
        "당기순이익(손실)":  [  2_644_124_219,   2_393_140_690,   1_950_338_772],
        "총포괄손익":       [  2_772_446_115,   2_442_009_884,   1_999_772_331],
    })},
    # 금융업 — 매출액·영업이익이 없다
    "kr-hanul-capital": {2025: dict(term=12, layout="financial", cfs={
        "자산총계":                  [1_884_119_772_446, 1_742_009_331_884, 1_557_446_115_009],
        "부채총계":                  [1_688_442_009_115, 1_566_119_772_331, 1_402_331_884_772],
        "자본금":                    [   80_000_000_000,    80_000_000_000,    70_000_000_000],
        "이익잉여금":                 [   92_557_331_009,    81_119_446_772,    69_442_115_884],
        "자본총계":                  [  195_677_763_331,   175_889_559_553,   155_114_230_237],
        "예수부채":                  [1_204_119_884_772, 1_118_442_331_009,   998_772_446_115],
        "당기손익-공정가치측정금융자산":   [  188_009_772_331,   172_557_115_886,   151_119_446_009],
        "파생상품자산":               [   12_442_115_884,    11_009_772_446,     9_880_331_115],
        "파생상품부채":               [   11_880_009_331,    10_557_446_772,     9_119_884_005],
        "순이자손익":                 [   58_119_446_772,    52_880_009_331,    46_442_115_884],
        "이자수익":                  [  112_557_331_009,   104_119_884_772,    94_772_446_115],
        "이자비용":                  [   54_437_884_237,    51_239_875_441,    48_330_330_231],
        "순수수료손익":               [   14_009_772_446,    12_557_331_884,    11_119_446_009],
        "영업이익(손실)":             [   26_880_115_331,    23_442_009_772,    19_772_446_884],
        "법인세차감전 순이익":          [   25_119_884_009,    22_009_446_331,    18_442_115_772],
        "당기순이익(손실)":            [   19_338_772_115,    16_880_446_009,    14_119_009_884],
        "총포괄손익":                [   19_772_009_446,    17_119_884_331,    14_442_115_005],
    }, ofs=None)},
}

# EDGAR — 태그별 시계열. val은 숫자, 기간은 start/end (edgar_gleif_quirks E4).
# 정정 보고가 남아 같은 기간이 두 번 나오는 것도 재현한다.
EDGAR_FACTS = {
    "us-northgate-cells": {
        "Revenues": [
            dict(start="2023-01-01", end="2023-12-31", val=812_440_000, accn="9900000101-24-000012",
                 fy=2023, fp="FY", form="10-K", filed="2024-02-21", frame="CY2023"),
            dict(start="2024-01-01", end="2024-12-31", val=1_004_118_000, accn="9900000101-25-000009",
                 fy=2024, fp="FY", form="10-K", filed="2025-02-19", frame="CY2024"),
            # ↓ 같은 기간의 최초 보고와 정정. accn이 다르다. 중복 제거 안 하면 이중 계상
            dict(start="2025-01-01", end="2025-12-31", val=1_188_552_000, accn="9900000101-26-000007",
                 fy=2025, fp="FY", form="10-K", filed="2026-02-18", frame="CY2025"),
            dict(start="2025-01-01", end="2025-12-31", val=1_181_907_000, accn="9900000101-26-000031",
                 fy=2025, fp="FY", form="10-K/A", filed="2026-05-07"),
        ],
        "Assets": [
            dict(start=None, end="2024-12-31", val=2_233_881_000, accn="9900000101-25-000009",
                 fy=2024, fp="FY", form="10-K", filed="2025-02-19", frame="CY2024Q4I"),
            dict(start=None, end="2025-12-31", val=2_551_004_000, accn="9900000101-26-000007",
                 fy=2025, fp="FY", form="10-K", filed="2026-02-18", frame="CY2025Q4I"),
        ],
        "NetIncomeLoss": [
            dict(start="2024-01-01", end="2024-12-31", val=-44_119_000, accn="9900000101-25-000009",
                 fy=2024, fp="FY", form="10-K", filed="2025-02-19", frame="CY2024"),
            dict(start="2025-01-01", end="2025-12-31", val=58_772_000, accn="9900000101-26-000007",
                 fy=2025, fp="FY", form="10-K", filed="2026-02-18", frame="CY2025"),
        ],
    }
}


# ---------------------------------------------------------------- 합계 정합
def normalize_financials():
    """합계 계정을 구성 계정에서 다시 계산해 회계 항등식을 강제한다.

    손으로 쓴 값은 leaf(유동/비유동, 자본금·이익잉여금 등)만 신뢰하고,
    자산총계·부채총계·자본총계는 여기서 덮어쓴다. 픽스처를 손볼 때
    합계를 같이 고쳐야 하는 부담을 없앤다.
    """
    for cid, years in FINANCIALS.items():
        for y, d in years.items():
            for div in ("cfs", "ofs"):
                a = d.get(div)
                if not a:
                    continue
                if d["layout"] == "manufacturing":
                    a["자산총계"] = [x + y_ for x, y_ in zip(a["유동자산"], a["비유동자산"])]
                    a["부채총계"] = [x + y_ for x, y_ in zip(a["유동부채"], a["비유동부채"])]
                a["자본총계"] = [x - y_ for x, y_ in zip(a["자산총계"], a["부채총계"])]
                assert all(t == l + e for t, l, e in
                           zip(a["자산총계"], a["부채총계"], a["자본총계"])), (cid, y, div)


normalize_financials()


# ---------------------------------------------------------------- 공급망
# tier 컬럼 없음. n차는 재귀 조인의 결과로만 정의된다.
# share_pct는 buyer 기준 조달 비중. confidence는 관측 근거 수준.
EDGE_COLUMNS = ["buyer_id", "supplier_id", "relation_type", "hs_code", "item",
                "share_pct", "since", "until", "observed_in", "source",
                "as_of", "confidence"]

EDGES = [
    # 최종 고객 ← 기준사
    ("us-northgate-cells", "kr-hanul-materials", "supplier", "850760", "양극재 전구체",
     22.5, "2022-04", "", "customs+bol", "customs_kr+bol_us", AS_OF, 0.88),
    ("us-northgate-cells", "cn-jinhe-chem", "supplier", "282690", "리튬염",
     9.0, "2023-06", "", "bol", "bol_us", AS_OF, 0.52),
    ("us-northgate-cells", "kr-sungjin-precision", "contract_manufacturer", "847989", "전극 조립 설비",
     6.0, "2024-02", "", "filing", "filings/us", AS_OF, 0.48),

    # 기준사 ← 1차
    ("kr-hanul-materials", "kr-daejin-chem", "supplier", "290369", "전해액 첨가제",
     34.0, "2021-03", "", "customs+bol", "customs_kr+bol_us", AS_OF, 0.86),
    ("kr-hanul-materials", "cn-jinhe-chem", "supplier", "282690", "리튬염",
     41.5, "2020-11", "", "customs", "customs_kr", AS_OF, 0.79),
    # ↓ 공급사가 GLEIF상 INACTIVE인데 엣지는 종료 표시가 없다 — 유령 엣지
    ("kr-hanul-materials", "jp-sakuragawa-kasei", "supplier", "390940", "바인더 수지",
     12.0, "2019-06", "", "filing", "filings/kr", AS_OF, 0.61),
    ("kr-hanul-materials", "kr-sungjin-precision", "contract_manufacturer", "847989", "전극 코팅 설비",
     8.5, "2023-01", "", "filing", "filings/kr", AS_OF, 0.72),

    # 1차 ← 2차. 제재 대상이 여기 숨어 있다
    ("cn-jinhe-chem", "cn-beifang-lithium", "supplier", "282520", "탄산리튬",
     58.0, "2021-08", "", "customs+bol", "customs_kr+bol_us", AS_OF, 0.81),
    ("cn-jinhe-chem", "cn-beifeng-lithium", "supplier", "282520", "수산화리튬",
     24.0, "2022-02", "", "customs", "customs_kr", AS_OF, 0.64),
    ("kr-daejin-chem", "kr-sungjin-precision", "supplier", "848180", "정밀 밸브",
     19.0, "2022-05", "", "filing", "filings/kr", AS_OF, 0.70),
    ("kr-daejin-chem", "cn-beifeng-lithium", "supplier", "282520", "수산화리튬",
     31.0, "2023-03", "", "customs", "customs_kr", AS_OF, 0.58),
    # ↓ 종료된 거래 + 낮은 confidence. 뉴스 1건이 유일한 근거
    ("kr-daejin-chem", "cn-beifang-lithium", "supplier", "282520", "탄산리튬",
     15.0, "2024-01", "2025-11", "news", "news/2025/11", AS_OF, 0.28),

    # 순환 참조: daejin → sungjin → sakuragawa → daejin
    ("kr-sungjin-precision", "jp-sakuragawa-kasei", "supplier", "390940", "이형 필름",
     27.0, "2021-09", "", "filing", "filings/kr", AS_OF, 0.66),
    ("jp-sakuragawa-kasei", "kr-daejin-chem", "supplier", "290369", "용제",
     11.5, "2020-02", "", "customs", "customs_kr", AS_OF, 0.55),

    # 2차 ← 3차. 자체는 깨끗하나 모회사가 제재 대상
    ("cn-beifang-lithium", "cn-yuxi-mining", "supplier", "253090", "리튬 정광",
     44.0, "2019-05", "", "customs", "customs_kr", AS_OF, 0.74),
    ("cn-beifeng-lithium", "cn-yuxi-mining", "supplier", "253090", "리튬 정광",
     38.0, "2020-07", "", "customs", "customs_kr", AS_OF, 0.69),

    # 동명이인 쪽 그래프. 이름으로 조회하면 여기가 섞여 들어온다
    ("kr-daejin-chem-cosmetic", "kr-sungjin-precision", "supplier", "761519", "알루미늄 용기 부품",
     12.0, "2023-08", "", "filing", "filings/kr", AS_OF, 0.44),
    ("kr-daejin-chem-cosmetic", "cn-beifeng-lithium", "supplier", "382499", "계면활성제",
     7.5, "2024-05", "", "customs", "customs_kr", AS_OF, 0.39),
]

# ---------------------------------------------------------------- 소유
# GLEIF 관계 레코드에는 지분율이 없다(edgar_gleif_quirks G5).
# share_pct는 우리가 추가한 필드이고, 그 사실을 `basis`에 남긴다.
OWNERSHIP_COLUMNS = ["parent_id", "child_id", "share_pct", "basis",
                     "gleif_rr", "as_of", "note"]
OWNERSHIP = [
    ("cn-tianyuan-holdings", "cn-yuxi-mining", 68.0, "filing-disclosed", "yes", AS_OF,
     "모회사가 제재 대상. 자회사 자체는 명단에 없다"),
    ("kr-hanul-materials", "kr-hanul-capital", 51.0, "filing-disclosed", "yes", AS_OF,
     "연결 대상 금융 자회사"),
    # ↓ 피출자사에 LEI가 없어 GLEIF 관계 레코드로는 표현되지 않는다
    ("kr-hanul-materials", "kr-sungjin-precision", 30.0, "filing-disclosed", "no", AS_OF,
     "지분 30%. 성진정밀에 LEI가 없어 gleif_rr.jsonl에는 대응 레코드가 없다"),
]

# ---------------------------------------------------------------- 제재
# OFAC SDN 형식만 차용. 대상은 전부 가공이고 list_name을 MOCK-*로 못박는다.
# company_id 매핑은 일부러 두지 않는다 — 이름 매칭은 에이전트의 일이다.
SANCTIONS_COLUMNS = ["list_name", "entity_name", "aliases", "country",
                     "program", "listed_on", "source"]
SANCTIONS = [
    # ↓ 실제 상호는 "Beifang Lithium Materials Co., Ltd."
    #   MATERIAL(단수) + INDUSTRIAL 삽입 + 법인격 접미사 없음 → 정확 일치가 안 된다
    ("MOCK-SDN", "BEIFANG LITHIUM MATERIAL INDUSTRIAL CO",
     "BEIFANG LITHIUM MATERIAL IND;北方锂业材料;BFLM", "CN",
     "MOCK-NPWMD", "2024-11-14", "mock-ofac-sdn"),
    ("MOCK-SDN", "TIANYUAN HOLDINGS LIMITED",
     "TIANYUAN HLDG LTD;天源控股;TIANYUAN GROUP", "CN",
     "MOCK-NPWMD", "2025-03-06", "mock-ofac-sdn"),
    # 이하 노이즈. 그래프에 걸리지 않는다
    ("MOCK-SDN", "ORONTES SHIPPING AND TRADING LLC",
     "ORONTES SHIPPING;ORONTES TRD", "SY", "MOCK-SDGT", "2023-05-30", "mock-ofac-sdn"),
    ("MOCK-SDN", "VOSTOK PRIBOR OAO",
     "VOSTOK PRIBOR;ВОСТОК ПРИБОР", "RU", "MOCK-RUSSIA-EO14024", "2024-02-23", "mock-ofac-sdn"),
    ("MOCK-EU-CONSOLIDATED", "KARAKUM METALS JSC",
     "KARAKUM METAL;KARAKUM METALLURGY", "TM", "MOCK-EU-DUAL-USE", "2025-07-11", "mock-eu-consolidated"),
    ("MOCK-EU-CONSOLIDATED", "PT SAMUDRA LOGISTIK NUSANTARA",
     "SAMUDRA LOGISTIK;PT SLN", "ID", "MOCK-EU-DUAL-USE", "2024-09-19", "mock-eu-consolidated"),
    ("MOCK-SDN", "NORTHERN LITHIUM TRADING FZE",
     "NORTHERN LITHIUM;NLT FZE", "AE", "MOCK-NPWMD", "2025-01-22", "mock-ofac-sdn"),
]

# ---------------------------------------------------------------- 모니터링 대상
WATCHLIST = ["kr-hanul-materials", "kr-daejin-chem", "kr-sungjin-precision",
             "cn-jinhe-chem", "cn-beifang-lithium", "us-northgate-cells"]

# ---------------------------------------------------------------- 참조 테이블
# 업종 코드는 소스마다 체계가 다르고 1:1이 아니다(dart_quirks ⑧, edgar E7).
# ksic 자릿수가 3과 5로 섞여 있는 것도 실물 그대로다.
INDUSTRY_XWALK = [
    ("20119", "2819", "325180", "기타 기초 무기화학물질 제조업"),
    ("201",   "2819", "325180", "기초 화학물질 제조업 (소분류)"),
    ("201",   "2821", "325211", "기초 화학물질 제조업 (소분류) — 대응 복수"),
    ("20431", "2844", "325620", "화장품 제조업"),
    ("29199", "3559", "333249", "기타 특수 목적용 기계 제조업"),
    ("64992", "6159", "522298", "그 외 기타 여신 금융업"),
    ("26299", "3691", "335910", "축전지 제조업"),
]

# 의도된 구멍: JPY 2026-05가 없다. 인접 월로 대체하면 안 된다.
FX_MONTHS = ["2024-12", "2025-03", "2025-06", "2025-09", "2025-12",
             "2026-03", "2026-05", "2026-06"]
FX_RATES = {
    "USD": [1_432.10, 1_468.55, 1_389.20, 1_355.70, 1_401.35, 1_378.90, 1_366.25, 1_359.80],
    "CNY": [   196.40,   201.15,   192.85,   188.30,   194.05,   191.20,   189.55,   188.70],
    "JPY": [     9.12,     9.44,     9.05,     8.88,     9.21,     9.03,     None,     8.95],
}
