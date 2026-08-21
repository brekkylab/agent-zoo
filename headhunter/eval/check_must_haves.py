"""`must_haves.json` 의 `expected_qualified` 가 실제 DB 와 맞는지.

**손으로 적은 수는 데이터가 바뀌면 썩는다.** 이 프로젝트에서 그 실패가 반복됐다 —
`58/600` 이 `56/600` 이 됐는데 주석 세 곳에 남았고, 정의가 없어 아무도 재검증할 수
없었다. 조건을 기계 판독 가능하게 적어 둔 이유가 이것이고, 이 스크립트가 그 조건을
실제로 돌려 수를 다시 센다.
"""

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE.parent / "data" / "headhunter.db"


def where(cond: dict) -> tuple[str, list]:
    """한 조건을 SQL 조각으로. `b` 는 `candidate_brief` 별칭이다."""
    kind, value = cond["kind"], cond["value"]
    if kind == "city_in":
        return f"b.city IN ({','.join('?' * len(value))})", list(value)
    if kind == "profile_language":
        return "b.profile_language = ?", [value]
    if kind == "real_months_at_least":
        # `candidate_brief` 는 real_years 만 갖는다. 개월은 tenure VIEW 에서 온다.
        return "(SELECT real_months FROM candidate_tenure t WHERE t.id = b.id) >= ?", [value]
    if kind == "skill_matches":
        return ("EXISTS (SELECT 1 FROM skills s WHERE s.candidate_id = b.id "
                "AND LOWER(s.name) LIKE ?)", [value])
    if kind == "skill_any_of":
        # **표기 변이를 전부 받는다.** 데이터셋이 같은 스킬을 `Rust`·`rust-lang`·
        # `러스트`·`Tokio` 로 적고(spec §3.4), 지침은 에이전트에게 그렇게 넓히라고
        # 지시한다. 게이트가 `LIKE '%rust%'` 로 좁으면 지침이 시킨 행동으로 찾은
        # 사람이 게이트에서 사라진다.
        #
        # 게이트와 정독의 분업이기도 하다. 게이트는 **넓게 통과**시키고, "실무인가"
        # 는 포지션 설명을 읽어 가린다 — 실제 실행에서 에이전트가 Tokio 보유자
        # 하나를 그렇게 걸러냈고, 그 판단은 스킬 태그가 아니라 설명에 근거했다.
        return (f"EXISTS (SELECT 1 FROM skills s WHERE s.candidate_id = b.id "
                f"AND s.name IN ({','.join('?' * len(value))}))", list(value))
    if kind == "skills_all":
        return (f"(SELECT COUNT(DISTINCT s.name) FROM skills s WHERE s.candidate_id = b.id "
                f"AND s.name IN ({','.join('?' * len(value))})) = {len(value)}", list(value))
    raise SystemExit(f"모르는 조건 종류: {kind!r}")


def main() -> int:
    con = sqlite3.connect(DB)
    spec = json.loads((HERE / "jd" / "must_haves.json").read_text())
    violations = []

    for jd, entry in spec.items():
        if jd.startswith("_"):
            continue
        clauses, params = [], []
        for cond in entry["conditions"]:
            sql, args = where(cond)
            clauses.append(sql)
            params += args
        n = con.execute(
            f"SELECT COUNT(*) FROM candidate_brief b WHERE {' AND '.join(clauses)}", params
        ).fetchone()[0]

        said = entry["expected_qualified"]
        k = entry["k"]
        mark = " " if n == said else "X"
        shape = "적게 냄" if n < k else "좁혀야 함"
        print(f"  {mark} {jd:22} 실제 {n:3}  기록 {said:3}  k={k:2}  {shape}")
        if n != said:
            violations.append(f"{jd}: 조건이 {n}명을 내는데 expected_qualified 는 {said}")
        # 이 JD 가 시험하려는 것이 무엇인지가 이 부등식으로 갈린다. 뒤집히면
        # `run_eval.py` 의 채점 기준이 통째로 바뀐다.
        if (n < k) != (said < k):
            violations.append(f"{jd}: 실제와 기록이 k={k} 의 양쪽으로 갈린다 — 검증 대상이 다르다")

        # JD 파일이 실재하는지도 본다. 없으면 에이전트에게 줄 것이 없다.
        if not (HERE / "jd" / f"{jd}.md").exists():
            violations.append(f"{jd}: eval/jd/{jd}.md 가 없다")

    if violations:
        print(f"\n위반 {len(violations)}건")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("\n위반 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
