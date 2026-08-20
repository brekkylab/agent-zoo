"""정답 경로 검증 — ground_truth.yaml의 14케이스를 실제로 풀어본다.

에이전트를 대신해 사람이 손으로 푸는 경로를 코드로 고정한 것이다.
목적은 두 가지.

1. **데이터가 답을 내놓는가.** 케이스가 도달 불가능하면 에이전트를 붙여도 못 푼다.
   스키마를 바꾸는 비용은 지금이 제일 싸다.
2. **표준 라이브러리만으로 완주되는가.** duckdb/pandas를 쓰지 않는다.
   "duckdb는 최적화이지 전제가 아니다"를 여기서 증명한다.

실패하면 데이터가 틀린 것이다. 에이전트 성능과는 무관하다.
"""
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

DATA = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "data"))
results = []


def case(cid):
    def deco(fn):
        results.append((cid, fn))
        return fn
    return deco


def rd(rel):
    with open(os.path.join(DATA, rel), encoding="utf-8") as f:
        return f.read()


def rcsv(rel):
    return list(csv.DictReader(open(os.path.join(DATA, rel), encoding="utf-8")))


def rjson(rel):
    return json.loads(rd(rel))


def rjsonl(rel):
    return [json.loads(x) for x in rd(rel).splitlines() if x.strip()]


def amount(s):
    """DART 금액 문자열 -> int. 콤마 제거, 결측은 None."""
    return None if s == "" else int(s.replace(",", ""))


def norm_name(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---------------------------------------------------------------- 공통 준비
INDEX = {r["company_id"]: r for r in rcsv("registry/company_index.csv")}
GLEIF = {r["lei"]: r for r in rjsonl("registry/gleif_lei.jsonl")}
EDGES = rcsv("supplychain/edges.csv")
SANCTIONS = rcsv("risk/sanctions.csv")
OWNERSHIP = rcsv("registry/ownership.csv")
ROOT = "kr-hanul-materials"

ADJ = {}
for e in EDGES:
    ADJ.setdefault(e["buyer_id"], []).append(e)


def expand(root, max_depth=5):
    """공급망 n차 전개. 방문 가드가 없으면 순환에서 안 끝난다."""
    out, stack = {}, [(root, 0, (root,))]
    while stack:
        node, depth, path = stack.pop()
        if depth and (node not in out or depth < out[node][0]):
            out[node] = (depth, path)
        if depth >= max_depth:
            continue
        for e in ADJ.get(node, []):
            if e["supplier_id"] in path:        # ← 가드
                continue
            stack.append((e["supplier_id"], depth + 1, path + (e["supplier_id"],)))
    return out


TIERS = expand(ROOT)


def name_en(cid):
    l = INDEX[cid]["lei"]
    return GLEIF[l]["entity"]["otherNames"][0]["name"] if l else None


def sanction_candidates(cid, min_prefix=12):
    """제재 명단 후보 추출. 정확 일치는 안 되므로 접두 일치로 후보만 낸다."""
    en = name_en(cid)
    if not en:
        return []
    b = norm_name(en)
    hits = []
    for s in SANCTIONS:
        names = [s["entity_name"]] + s["aliases"].split(";")
        for n in names:
            a = norm_name(n)
            if len(a) >= min_prefix and len(b) >= min_prefix and a[:min_prefix] == b[:min_prefix]:
                hits.append((s, n))
                break
    return hits


# ---------------------------------------------------------------- 케이스
@case("sanctions-tier2-alias")
def _():
    hits = sanction_candidates("cn-beifang-lithium")
    assert hits, "2차 제재 후보가 안 잡힌다"
    s, matched = hits[0]
    depth, path = TIERS["cn-beifang-lithium"]
    assert depth == 2, f"2차여야 한다 (실제 {depth}차)"
    assert name_en("cn-beifang-lithium") != s["entity_name"], "정확 일치하면 함정이 죽는다"
    return (f"{depth}차 {path[1]} 경유 / data={name_en('cn-beifang-lithium')!r} "
            f"list={s['entity_name']!r} [{s['program']}] — 정확 일치 아님")


@case("sanctions-tier3-via-parent")
def _():
    child = "cn-yuxi-mining"
    assert TIERS[child][0] == 3, "3차여야 한다"
    assert not sanction_candidates(child), "자회사 자체는 명단에 없어야 한다"
    own = [o for o in OWNERSHIP if o["child_id"] == child]
    assert own, "소유 관계가 없다"
    o = own[0]
    hits = sanction_candidates(o["parent_id"])
    assert hits, "모회사가 명단에 잡혀야 한다"
    rr = [r for r in rjsonl("registry/gleif_rr.jsonl")
          if r["relationship"]["startNode"]["id"] == INDEX[child]["lei"]]
    assert all("share_pct" not in json.dumps(r) for r in rr), "GLEIF에 지분율이 있으면 안 된다"
    return (f"3차 {child} ← 지분 {o['share_pct']}% ← {o['parent_id']} "
            f"[{hits[0][0]['entity_name']}] / 지분율 출처={o['basis']}, GLEIF에는 없음")


@case("false-positive-beifeng")
def _():
    cid = "cn-beifeng-lithium"
    en = name_en(cid)
    exact = [s for s in SANCTIONS if norm_name(s["entity_name"]) == norm_name(en)]
    assert not exact, "미끼가 명단에 정확 일치하면 안 된다"
    # 접두 일치로는 안 걸린다. 편집거리 기반 퍼지 매칭이 오탐을 낸다
    other = norm_name(name_en("cn-beifang-lithium"))
    d = edit_distance(norm_name(en), other)
    assert d <= 2, f"Beifang과 편집거리가 {d}라 미끼 구실을 못 한다"
    listed = norm_name(SANCTIONS[0]["entity_name"])
    d2 = min(edit_distance(norm_name(n), norm_name(en))
             for n in [SANCTIONS[0]["entity_name"]] + SANCTIONS[0]["aliases"].split(";"))
    return (f"{en!r} 정확일치 0건 / 실제 제재사 Beifang과 편집거리 {d} "
            f"— 퍼지 매칭 임계값이 느슨하면 오탐 (명단 표기와는 {d2})")


@case("homonym-daejin")
def _():
    xml = ET.fromstring(rd("registry/dart_corpcode.xml"))
    same = [e for e in xml if e.findtext("corp_name") == "대진화학"]
    assert len(same) == 2, f"동명이인 2건이어야 한다 (실제 {len(same)})"
    profiles = []
    for e in same:
        d = rjson(f"registry/dart_company/{e.findtext('corp_code')}.json")
        profiles.append((d["corp_code"], d["corp_name"], d["induty_code"], d["est_dt"],
                         d["adres"].split()[0]))
    assert profiles[0][2] != profiles[1][2], "업종이 같으면 구분 근거가 없다"
    return " / ".join(f"{c} {n} 업종{i} 설립{e} {a}" for c, n, i, e, a in profiles)


@case("cfs-ofs-mixed")
def _():
    rows = rjson("financials/dart_fnltt/99000101-2025.json")["list"]
    rev = {r["fs_div"]: amount(r["thstrm_amount"])
           for r in rows if r["account_nm"] == "매출액"}
    assert set(rev) == {"CFS", "OFS"}, "한 파일에 연결·별도가 함께 있어야 한다"
    gap = (rev["CFS"] - rev["OFS"]) / rev["CFS"] * 100
    assert gap > 10, "차이가 너무 작으면 함정이 안 된다"
    return f"CFS {rev['CFS']:,} / OFS {rev['OFS']:,} — {gap:.1f}% 차이. 기준 명시 필수"


@case("duplicate-net-income")
def _():
    rows = [r for r in rjson("financials/dart_fnltt/99000101-2025.json")["list"]
            if r["fs_div"] == "CFS" and r["account_nm"] == "당기순이익(손실)"]
    assert len(rows) == 2, "ord 29/61 두 건이어야 한다"
    naive = sum(amount(r["thstrm_amount"]) for r in rows)
    correct = amount(rows[0]["thstrm_amount"])
    assert naive == correct * 2
    return (f"ord {[r['ord'] for r in rows]} / 정답 {correct:,} "
            f"but 순진한 합산 {naive:,} (2배)")


@case("financial-account-schema")
def _():
    rows = rjson("financials/dart_fnltt/99000512-2025.json")["list"]
    names = {r["account_nm"] for r in rows}
    assert "매출액" not in names and "영업이익" not in names
    assert "영업이익(손실)" in names and "순이자손익" in names
    op = next(amount(r["thstrm_amount"]) for r in rows
              if r["fs_div"] == "CFS" and r["account_nm"] == "영업이익(손실)")
    return f"매출액·영업이익 없음 / 영업이익(손실)={op:,}, 순이자손익·예수부채 체계"


@case("supply-chain-cycle")
def _():
    # 가드 없는 전개의 피해는 폭발이 아니라 (1) 종료되지 않음 (2) 같은 회사 중복 계상
    def no_guard(node, depth, limit, seen):
        seen.append(node)
        if depth >= limit:
            return
        for e in ADJ.get(node, []):
            no_guard(e["supplier_id"], depth + 1, limit, seen)

    a, b = [], []
    no_guard(ROOT, 0, 10, a)
    no_guard(ROOT, 0, 20, b)
    assert len(b) > len(a), f"깊이를 늘려도 안 늘면 순환이 없는 것 ({len(a)}/{len(b)})"
    from collections import Counter
    dup = Counter(a).most_common(1)[0]
    assert dup[1] > 1, "중복 방문이 없으면 순환이 없는 것"
    # 매직넘버 대신 무엇이 들어오고 무엇이 안 들어오는지로 검증한다
    assert {"cn-beifang-lithium", "cn-yuxi-mining", "jp-sakuragawa-kasei"} <= set(TIERS), \
        "리스크 노드가 전개에 들어와야 한다"
    assert "kr-daejin-chem-cosmetic" not in TIERS, "동명이인 법인은 공급망에 없다"
    assert "kr-hanul-capital" not in TIERS, "금융 자회사는 공급망에 없다"
    return (f"가드 있음 → {len(TIERS)}노드로 수렴 / 없음 → 방문 {len(a)}회(깊이10) → "
            f"{len(b)}회(깊이20), 종료 조건 없음. "
            f"{dup[0]}가 {dup[1]}회 중복 방문 → share_pct 중복 계상")


@case("missing-lei-sungjin")
def _():
    cid = "kr-sungjin-precision"
    assert INDEX[cid]["lei"] == "", "LEI가 비어 있어야 한다"
    assert not any(o for o in rjsonl("registry/gleif_lei.jsonl")
                   if o["entity"]["registeredAs"] == "999-40-03456")
    own = [o for o in OWNERSHIP if o["child_id"] == cid][0]
    assert own["gleif_rr"] == "no"
    return (f"지분 {own['share_pct']}% 관계가 ownership.csv에만 있고 "
            f"gleif_rr.jsonl에는 없음 (LEI 미보유) — 데이터 한계로 보고해야 함")


@case("missing-fy2025-sungjin")
def _():
    d = os.path.join(DATA, "financials/dart_fnltt")
    files = [f for f in os.listdir(d) if f.startswith("99000427-")]
    years = sorted(int(f.split("-")[1].split(".")[0]) for f in files)
    assert 2025 not in years and 2024 in years
    rows = rjson(f"financials/dart_fnltt/99000427-2024.json")["list"]
    rev = next(amount(r["thstrm_amount"]) for r in rows if r["account_nm"] == "매출액")
    return f"보유 연도 {years} — FY2025 없음. 최신은 FY2024 매출 {rev:,}. 외삽 금지"


@case("ghost-edge-dissolved")
def _():
    cid = "jp-sakuragawa-kasei"
    g = GLEIF[INDEX[cid]["lei"]]["entity"]
    assert g["status"] == "INACTIVE"
    assert g["expiration"]["date"] is None, "소멸 시점이 비어 있어야 실물과 같다"
    live = [e for e in EDGES if e["supplier_id"] == cid and e["until"] == ""]
    assert live, "종료 표시 없는 엣지가 있어야 한다"
    return (f"GLEIF status=INACTIVE, expiration=null / "
            f"until 없는 공급 엣지 {len(live)}건 (buyer: {[e['buyer_id'] for e in live]})")


@case("fx-gap-jpy")
def _():
    fx = rcsv("reference/fx_rates.csv")
    months = {r["month"] for r in fx if r["from_currency"] == "JPY"}
    assert "2026-05" not in months and "2026-06" in months
    return f"JPY 보유 월 {sorted(months)} — 2026-05 없음. 인접 월 대체 금지"


@case("bizr-no-join-format")
def _():
    joined, raw = 0, 0
    for cid, r in INDEX.items():
        if not r["corp_code"] or not r["lei"]:
            continue
        d = rjson(f"registry/dart_company/{r['corp_code']}.json")
        g = GLEIF[r["lei"]]["entity"]["registeredAs"]
        raw += d["bizr_no"] == g
        joined += d["bizr_no"] == g.replace("-", "")
    assert joined == 4 and raw == 0
    return f"정규화 후 {joined}/4 조인 / 원문 그대로 {raw}건 — 하이픈 제거 필수"


@case("low-confidence-edge")
def _():
    e = [x for x in EDGES if x["buyer_id"] == "kr-daejin-chem"
         and x["supplier_id"] == "cn-beifang-lithium"][0]
    assert float(e["confidence"]) < 0.35 and e["until"] and e["observed_in"] == "news"
    return (f"confidence={e['confidence']}, 근거={e['observed_in']}, "
            f"거래 종료={e['until']} — 진행 중으로 쓰면 오답")


# ---------------------------------------------------------------- 실행
if __name__ == "__main__":
    fails = 0
    print(f"정답 경로 검증 — {len(results)}케이스 (표준 라이브러리만 사용)\n")
    for cid, fn in results:
        try:
            print(f"  PASS  {cid}\n        {fn()}")
        except AssertionError as ex:
            fails += 1
            print(f"  FAIL  {cid}\n        {ex}")
    print(f"\n통과 {len(results) - fails} / 실패 {fails}")
    sys.exit(1 if fails else 0)
