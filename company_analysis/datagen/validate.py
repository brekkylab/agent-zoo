"""data/ 무결성 검사. 합성 12사 데이터셋 전체가 대상이다.

의도한 함정과 실수를 구별하는 게 요점이다. 의도된 결측·불일치는
fixtures에 등록되어 있어야만 통과한다.
"""
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures as F  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "data"))
errors, notes = [], []


def chk(cond, msg):
    (notes if cond else errors).append(msg)


def rd(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def rcsv(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rjsonl(rel):
    return [json.loads(x) for x in rd(rel).splitlines() if x.strip()]


index = rcsv("registry/company_index.csv")
ids = {r["company_id"] for r in index}
by_id = {c["company_id"]: c for c in F.COMPANIES}

# ---- 1. 참조 무결성 -------------------------------------------------------
chk(len(index) == 12, f"company_index 12행 (실제 {len(index)})")
for e in rcsv("supplychain/edges.csv"):
    chk(e["buyer_id"] in ids, f"edges.buyer_id 미등록: {e['buyer_id']}")
    chk(e["supplier_id"] in ids, f"edges.supplier_id 미등록: {e['supplier_id']}")
for o in rcsv("registry/ownership.csv"):
    chk(o["parent_id"] in ids and o["child_id"] in ids,
        f"ownership 미등록 참조: {o['parent_id']}->{o['child_id']}")

# ---- 1b. CSV 컬럼 arity ---------------------------------------------------
# 값을 하나 빠뜨리면 컬럼이 통째로 밀리는데 DictReader는 조용히 None을 준다.
for rel in ("supplychain/edges.csv", "registry/ownership.csv", "risk/sanctions.csv",
            "registry/company_index.csv", "reference/fx_rates.csv",
            "reference/industry_xwalk.csv", "watchlist.csv"):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    widths = {len(r) for r in rows[1:]}
    chk(widths == {len(rows[0])},
        f"{rel} 컬럼 수 불일치: header {len(rows[0])} vs rows {sorted(widths)}")
for src, cols in ((F.EDGES, F.EDGE_COLUMNS), (F.OWNERSHIP, F.OWNERSHIP_COLUMNS),
                  (F.SANCTIONS, F.SANCTIONS_COLUMNS)):
    chk(all(len(t) == len(cols) for t in src),
        f"fixtures 튜플 길이가 컬럼 수({len(cols)})와 다르다")

# ---- 2. 원천 스키마 준수 --------------------------------------------------
DART_COMPANY_KEYS = {
    "status", "message", "corp_code", "corp_name", "corp_name_eng", "stock_name",
    "stock_code", "ceo_nm", "corp_cls", "jurir_no", "bizr_no", "adres", "hm_url",
    "ir_url", "phn_no", "fax_no", "induty_code", "est_dt", "acc_mt"}
for r in index:
    if not r["corp_code"]:
        continue
    d = json.loads(rd(f"registry/dart_company/{r['corp_code']}.json"))
    chk(set(d) == DART_COMPANY_KEYS,
        f"{r['corp_code']} DART 필드 집합 불일치: {set(d) ^ DART_COMPANY_KEYS}")
    chk(all(isinstance(v, str) for v in d.values()),
        f"{r['corp_code']} DART 값이 전부 STRING이어야 한다")
    chk(len(d["est_dt"]) == 8 and d["est_dt"].isdigit(), f"{r['corp_code']} est_dt YYYYMMDD")
    chk(d["corp_cls"] in "YKNE" and len(d["corp_cls"]) == 1, f"{r['corp_code']} corp_cls")

# ---- 3. 회계 항등식 + 금액 표기 -------------------------------------------
fin_dir = os.path.join(ROOT, "financials/dart_fnltt")
for fn in sorted(os.listdir(fin_dir)):
    rows = json.loads(rd(f"financials/dart_fnltt/{fn}"))["list"]
    for it in rows:
        for k in ("thstrm_amount", "frmtrm_amount", "bfefrmtrm_amount"):
            v = it[k]
            chk(v == "" or (v.lstrip("-").replace(",", "").isdigit()),
                f"{fn} {k} 표기 이상: {v!r}")
            chk("(" not in v, f"{fn} 음수는 괄호가 아니라 '-' 접두여야 한다: {v!r}")
    for div in ("CFS", "OFS"):
        acc = {}
        for it in rows:
            if it["fs_div"] == div and it["sj_div"] == "BS":
                acc[it["account_nm"]] = int(it["thstrm_amount"].replace(",", ""))
        if {"자산총계", "부채총계", "자본총계"} <= set(acc):
            chk(acc["자산총계"] == acc["부채총계"] + acc["자본총계"],
                f"{fn} {div} 자산 != 부채 + 자본")

# ---- 4. 의도된 함정이 살아 있는가 -----------------------------------------
sam = json.loads(rd("financials/dart_fnltt/99000101-2025.json"))["list"]
chk({r["fs_div"] for r in sam} == {"CFS", "OFS"},
    "한울소재 응답에 CFS/OFS가 함께 있어야 한다 (fs_div 필터 무효 재현)")
chk(sum(1 for r in sam if r["fs_div"] == "CFS" and r["account_nm"] == "당기순이익(손실)") == 2,
    "당기순이익(손실)이 CFS에 2회(ord 29/61) 있어야 한다")

cap = json.loads(rd("financials/dart_fnltt/99000512-2025.json"))["list"]
chk("매출액" not in {r["account_nm"] for r in cap},
    "금융업(한울캐피탈)에 매출액이 없어야 한다")
chk("영업이익(손실)" in {r["account_nm"] for r in cap},
    "금융업은 '영업이익'이 아니라 '영업이익(손실)'")

xml = ET.fromstring(rd("registry/dart_corpcode.xml"))
names = [e.findtext("corp_name") for e in xml]
chk(names.count("대진화학") == 2, "corpCode.xml에 동명이인 '대진화학' 2건")
blanks = [e.findtext("stock_code") for e in xml if not e.findtext("stock_code").strip()]
chk(all(v == " " for v in blanks),
    "corpCode.xml 결측 stock_code는 빈 문자열이 아니라 공백 1자")

leis = {r["lei"] for r in rjsonl("registry/gleif_lei.jsonl")}
chk(by_id["kr-sungjin-precision"]["lei"] is None and len(leis) == 11,
    "성진정밀은 LEI가 없어야 한다 (GLEIF 11건)")
rr_children = {r["relationship"]["startNode"]["id"] for r in rjsonl("registry/gleif_rr.jsonl")}
chk(by_id["kr-hanul-capital"]["lei"] in rr_children, "한울캐피탈 관계 레코드 존재")
chk(all("share_pct" not in json.dumps(r) for r in rjsonl("registry/gleif_rr.jsonl")),
    "GLEIF 관계 레코드에 지분율이 있으면 안 된다")

fx = rcsv("reference/fx_rates.csv")
chk(not [r for r in fx if r["from_currency"] == "JPY" and r["month"] == "2026-05"],
    "JPY 2026-05는 의도된 결측이어야 한다")

sanc = rcsv("risk/sanctions.csv")
chk(all(r["list_name"].startswith("MOCK-") for r in sanc),
    "제재 목록은 전부 MOCK-* 이어야 한다")
chk(not any("BEIFENG" in r["entity_name"].upper() or "BEIFENG" in r["aliases"].upper()
            for r in sanc),
    "유사명 미끼(Beifeng)는 제재 명단에 없어야 한다")
chk("company_id" not in open(os.path.join(ROOT, "risk/sanctions.csv"),
                             encoding="utf-8").readline(),
    "제재 목록에 company_id 매핑이 미리 있으면 안 된다")

# ---- 5. LEI 체크섬 --------------------------------------------------------
for c in F.COMPANIES:
    if c["lei"]:
        chk(F.lei(c["lei"][:18]) == c["lei"], f"{c['company_id']} LEI 체크섬")

# ---- 6. 그래프 -------------------------------------------------------------
edges = rcsv("supplychain/edges.csv")
adj = {}
for e in edges:
    adj.setdefault(e["buyer_id"], []).append(e["supplier_id"])


def depth(node, seen=frozenset()):
    if node in seen:
        return 0
    return max((1 + depth(s, seen | {node}) for s in adj.get(node, [])), default=0)


chk(depth("kr-hanul-materials") >= 3, "기준사에서 3차 이상 전개 가능")


def has_cycle():
    WHITE, GREY, BLACK = 0, 1, 2
    color = {}

    def visit(n):
        color[n] = GREY
        for s in adj.get(n, []):
            if color.get(s, WHITE) == GREY:
                return True
            if color.get(s, WHITE) == WHITE and visit(s):
                return True
        color[n] = BLACK
        return False

    return any(visit(n) for n in adj if color.get(n, WHITE) == WHITE)


chk(has_cycle(), "공급망에 순환이 있어야 한다 (재귀 방문 가드 테스트용)")


# ---- 7. 국가별 식별자 형식 ------------------------------------------------
# GLEIF registeredAs는 각국 등록번호를 그대로 담는다. 형식이 나라마다 다르고,
# 국가 등록처(EDINET·CNINFO 등)와 이어 붙일 때 쓰는 조인 키다.
import re as _re  # noqa: E402

_ID_RULES = {
    "KR": (r"^\d{3}-\d{2}-\d{5}$", "사업자등록번호"),
    "JP": (r"^\d{13}$", "法人番号"),
    "CN": (r"^[0-9A-Z]{18}$", "统一社会信用代码"),
    "US": (r"^\d{2}-\d{7}$", "EIN"),
}
for r in rjsonl("registry/gleif_lei.jsonl"):
    cid = lei2id_ = next(c["company_id"] for c in F.COMPANIES if c["lei"] == r["lei"])
    country = by_id[cid]["country"]
    pat, label = _ID_RULES[country]
    val = r["entity"]["registeredAs"]
    chk(bool(_re.match(pat, val)), f"{cid} registeredAs가 {country} {label} 형식이 아니다: {val}")
    if country == "JP":
        chk(F.houjin_bango_check(val[1:]) == int(val[0]),
            f"{cid} 法人番号 체크섬 불일치: {val}")

print(f"검사 {len(errors) + len(notes)}건 / 통과 {len(notes)} / 실패 {len(errors)}")
for e in errors:
    print("  FAIL:", e)
sys.exit(1 if errors else 0)
