"""색인이 계획 B 의 가정대로 동작하는지 — 근사치가 아니라 진짜 FTS5 로.

계획 B 의 `variants.fts5_recall` 은 `sqlite3` 를 부르지 않는다. 손으로 자른 토큰을
**한 필드**에 대해서만 맞춰 본다. 이 스크립트는 같은 질문을 실제 색인에 던진다.

두 판정을 낸다.

  (1) 정답이 검색에 잡히는가 — 안 잡히면 채점이 무의미하다. **위반이다.**
  (2) 검색단계 함정이 검색에 잡히는가 — 안 잡히면 그 함정은 죽었다. **위반이다.**

그리고 축별 재현율의 근사치 대비 차이를 보고한다. 판정이 아니라 기록이다 — 실제 색인이
다섯 필드를 합치므로 실제 재현율이 더 높은 것이 정상이고, 차이가 **0 이면 오히려 의심해야
한다**(`candidate_fts` 에 `descriptions` 나 `summary` 가 안 들어갔다는 뜻이다).
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent
DB = HERE / "data" / "headhunter.db"

# 계획 B `variants.needle_for` 가 정한 토큰. 여기 다시 적는 이유는 `_datagen` 을
# import 하지 않기 위해서다 — 예제가 생성기에 의존하면 예제만 배포할 수 없다.
# 값이 갈라지면 이 스크립트가 재현율 차이로 드러낸다.
NEEDLES = {
    "Rust": "rust",
    "Kubernetes": "kubernetes",
    "Distributed Systems": "distributed",
    "Senior Backend Engineer": "backend",
    "Backend Engineer": "backend",
    "Seoul, KR": "seoul",
    "Tokyo, JP": "tokyo",
}

# 축별로 "그 축의 값" 을 어디서 읽는가. 근사치는 이 한 필드만 본다.
#
# **`location` 축은 여기 없다.** `candidate_fts` 가 색인하는 다섯 필드에 포지션의
# `location` 이 들어가지 않기 때문이다. 그것이 옳다 — 지역은 `candidates.city` 라는
# 정확한 컬럼이 있고 `WHERE city IN (...)` 이 전문 검색보다 정확하다. FTS 는 자유
# 텍스트를 위한 것이다.
#
# 틀린 것은 계획 B 의 측정 쪽이다. `variants.fts5_recall` 이 `Seoul, KR`·`Tokyo, JP`
# 를 재고 그 값을 "FTS5 재현율" 이라 불렀는데, 그 축은 애초에 FTS 로 검색되지 않는다.
# 실제로 잰 것은 "location 문자열에 seoul 토큰이 있는 비율" 이고 그것은 검색 재현율이
# 아니다. 실측: `MATCH 'seoul'` 은 402명 중 **1명**을 데려오고, 그 1명은 요약에
# 우연히 Seoul 이 들어간 사람이다.
FTS_AXES = {
    "Rust": "SELECT candidate_id, name FROM skills",
    "Kubernetes": "SELECT candidate_id, name FROM skills",
    "Distributed Systems": "SELECT candidate_id, name FROM skills",
    "Senior Backend Engineer": "SELECT candidate_id, title FROM positions",
    "Backend Engineer": "SELECT candidate_id, title FROM positions",
}

# 컬럼으로 찾는 축. 색인이 아니라 `WHERE` 로 검사한다.
COLUMN_AXES = {
    "Seoul, KR": ("city", ("Seoul", "Seongnam")),
    "Tokyo, JP": ("city", ("Tokyo",)),
}


def tokens(text: str) -> set[str]:
    """`unicode61` 이 자르는 대로. 계획 B `variants._tokens` 와 같은 규칙이다."""
    return {t for t in re.split(r"[^\w]+", text.lower(), flags=re.UNICODE) if t}


def match(con: sqlite3.Connection, needle: str) -> set[str]:
    """실제 색인에서 이 토큰이 데려오는 id.

    `MATCH` 양쪽에 테이블 이름을 그대로 쓴다 — 별칭은 `no such column` 으로 죽는다.
    """
    return {
        r[0] for r in con.execute(
            "SELECT id FROM candidate_fts WHERE candidate_fts MATCH ?", (needle,))
    }


def main() -> int:
    con = sqlite3.connect(DB)
    truth = {t["id"]: t for t in json.loads((HERE / "data" / "ground_truth.json").read_text())}
    violations: list[str] = []

    # ── (1) 축별 재현율: 근사치와 실제의 차이 ────────────────────────────
    print("FTS 축 — 근사치(한 필드) 대비 실제 색인(다섯 필드)\n")
    for canonical, sql in FTS_AXES.items():
        needle = NEEDLES[canonical]
        approx = {cid for cid, value in con.execute(sql) if value and needle in tokens(value)}
        real = match(con, needle)
        gained, lost = real - approx, approx - real
        print(f"  {canonical:26} needle={needle:12} 근사 {len(approx):3}  실제 {len(real):3}"
              f"  추가 +{len(gained):3}  빠짐 -{len(lost)}")
        if lost:
            # 근사치가 찾는데 실제가 못 찾으면 토크나이저 가정이 틀렸다는 뜻이다.
            violations.append(
                f"{canonical}: 근사치는 찾는데 실제 색인이 못 찾는 {len(lost)}명 "
                f"— 토크나이저 가정이 틀렸다: {sorted(lost)[:3]}")
        if not gained:
            violations.append(
                f"{canonical}: 다섯 필드로 늘어난 사람이 0명 — `candidate_fts` 에 "
                f"`summary`/`descriptions` 가 실제로 들어갔는지 확인하라")

    # ── (1b) 컬럼 축: 색인이 아니라 컬럼으로 찾는다 ──────────────────────
    #
    # 이 축들이 FTS 로 안 잡히는 것은 결함이 아니라 설계다. 확인할 것은 **컬럼 쪽이
    # 실제로 사람을 데려오는가** 이고, 그것이 0 이면 JD 의 지역 조건이 아무도 못 찾는다.
    print("\n컬럼 축 — 색인이 아니라 WHERE 로 찾는다\n")
    for canonical, (column, values) in COLUMN_AXES.items():
        placeholders = ",".join("?" * len(values))
        n = con.execute(
            f"SELECT COUNT(*) FROM candidates WHERE {column} IN ({placeholders})", values
        ).fetchone()[0]
        by_fts = len(match(con, NEEDLES[canonical]))
        print(f"  {canonical:26} {column} IN {values} → {n:3}명"
              f"   (참고: MATCH '{NEEDLES[canonical]}' 는 {by_fts}명 — 색인에 없는 축이다)")
        if n == 0:
            violations.append(
                f"{canonical}: {column} 로 찾아도 0명이다 — JD 의 지역 조건이 아무도 "
                f"못 찾는다")

    # ── (2) JD 별: 정답과 함정이 검색에 잡히는가 ──────────────────────────
    must = json.loads((HERE / "eval" / "jd" / "must_haves.json").read_text())
    print("\nJD 별 — 정답과 검색단계 함정이 색인에 잡히는가\n")
    for path in sorted((HERE / "eval" / "expected").glob("*.json")):
        exp = json.loads(path.read_text())
        jd = exp["jd"]
        needles = []
        for cond in must.get(jd, {}).get("conditions", []):
            kind = cond["kind"]
            if kind == "skills_all":
                needles += [NEEDLES.get(s, s.split()[0].lower()) for s in cond["value"]]
            elif kind == "skill_matches":
                needles.append(cond["value"].strip("%").lower())
            elif kind == "skill_any_of":
                # 표기 변이 목록. 각 표기의 **첫 토큰**이 그것을 찾는 needle 이다 —
                # `rust-lang` 은 `rust`, `러스트` 는 `러스트`, `Tokio` 는 `tokio`.
                for name in cond["value"]:
                    toks = [t for t in re.split(r"[^\w]+", name.lower()) if t]
                    if toks:
                        needles.append(toks[0])
            elif kind == "city_in":
                needles += [c.split(",")[0].lower() for c in cond["value"]]
            elif kind in ("real_months_at_least", "profile_language"):
                pass  # 색인이 아니라 컬럼으로 거르는 조건이다
            else:
                violations.append(f"{jd}: check_index 가 모르는 조건 종류 {kind!r}")
        if not needles:
            violations.append(f"{jd}: must_haves.json 에서 needle 을 뽑을 수 없다")
            continue

        # 에이전트가 실제로 할 검색: must-have 를 OR 로 넓게 훑고 좁힌다. AND 로 좁히면
        # 색인이 **데려올 수 있는 것**과 **데려오는 것**을 구별할 수 없다.
        reachable: set[str] = set()
        for needle in needles:
            reachable |= match(con, needle)

        must_reach = {e["id"] for e in exp.get("controls_that_must_not_be_rejected", [])}
        must_reach |= set(exp.get("acceptable_top_k", []))
        unreachable = must_reach - reachable

        traps = {e["trap"] for e in exp.get("traps_that_must_be_caught", []) if e.get("trap")}
        trap_ids = {i for i, t in truth.items() if t["trap"] in traps and t["jd"] == jd}
        trap_unreachable = trap_ids - reachable

        print(f"  {jd:22} needles={','.join(sorted(set(needles)))}")
        print(f"    {'색인이 데려오는 인원':22} {len(reachable)}")
        print(f"    {'정답+대조군':22} {len(must_reach):3}  잡히지 않음 {sorted(unreachable) or '없음'}")
        print(f"    {'검색단계 함정':22} {len(trap_ids):3}  잡히지 않음 {sorted(trap_unreachable) or '없음'}")

        if unreachable:
            violations.append(
                f"{jd}: 정답/대조군 {len(unreachable)}명이 색인에 안 잡힌다 — "
                f"채점이 무의미하다: {sorted(unreachable)}")
        if trap_unreachable:
            violations.append(
                f"{jd}: 검색단계 함정 {len(trap_unreachable)}명이 색인에 안 잡힌다 — "
                f"그 함정은 죽었고 채점은 '에이전트가 피했다' 로 읽는다: "
                f"{sorted(trap_unreachable)}")

    if violations:
        print(f"\n위반 {len(violations)}건")
        for v in violations:
            print(f"  - {v}")
        print("\n**위반이 나오면 데이터가 아니라 JD 를 고친다.** 함정이 색인에 안 잡히는 것은")
        print("변이를 너무 강하게 뿌렸다는 뜻이고, 그 함정이 걸려야 하는 JD 의 needle 을 그")
        print("사람이 가진 표기로 넓히는 것이 옳은 수정이다 — 데이터를 고치면 계획 B 의")
        print("실측 전체를 다시 돌려야 한다.")
        return 1
    print("\n위반 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
