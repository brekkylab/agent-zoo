"""`eval/expected/*.json` 이 실재하는 사람과 실재하는 함정을 가리키는지.

**오타 하나가 채점을 조용히 무의미하게 만든다.** 없는 id 를 `must_not_appear` 에 적으면
그 검사는 영원히 통과한다 — 에이전트가 무엇을 하든 그 id 는 숏리스트에 나타날 수 없다.

id 를 손으로 적었다가 8개 중 6개를 지어낸 적이 있다. 그래서 이 스크립트가 있다.
"""

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE.parent / "data" / "headhunter.db"
TRUTH = HERE.parent / "data" / "ground_truth.json"


def main() -> int:
    con = sqlite3.connect(DB)
    ids = {r[0] for r in con.execute("SELECT id FROM candidates")}
    truth = {t["id"]: t for t in json.loads(TRUTH.read_text())}
    must = json.loads((HERE / "jd" / "must_haves.json").read_text())
    violations = []

    for path in sorted((HERE / "expected").glob("*.json")):
        exp = json.loads(path.read_text())
        jd = exp["jd"]

        # 언급된 모든 id 를 한 자리에 모은다
        named: dict[str, str] = {}
        for i in exp.get("acceptable_top_k", []):
            named[i] = "acceptable_top_k"
        for section in ("must_not_appear", "traps_that_must_be_caught",
                        "controls_that_must_not_be_rejected"):
            for entry in exp.get(section, []):
                if isinstance(entry, dict) and entry.get("id"):
                    named[entry["id"]] = section

        missing = {i: where for i, where in named.items() if i not in ids}
        for i, where in missing.items():
            violations.append(f"{jd}: {where} 의 {i} 가 DB 에 없다")

        # 라벨이 정답지와 맞는지 — id 는 맞는데 다른 사람을 가리키는 경우를 잡는다
        for entry in exp.get("must_not_appear", []) + exp.get("traps_that_must_be_caught", []):
            i, said = entry.get("id"), entry.get("trap")
            if not i or i not in truth or said is None:
                continue
            actual = truth[i]["trap"]
            if actual != said:
                violations.append(
                    f"{jd}: {i} 를 {said!r} 라 했는데 정답지는 {actual!r} 다")
        for entry in exp.get("controls_that_must_not_be_rejected", []):
            i, said = entry.get("id"), entry.get("control_for")
            if not i or i not in truth:
                continue
            actual = truth[i]["control_for"]
            if actual != said:
                violations.append(
                    f"{jd}: {i} 를 {said!r} 의 대조군이라 했는데 정답지는 {actual!r} 다")

        # k 가 must_haves.json 과 같아야 한다. 갈리면 두 파일이 다른 시험을 한다
        if jd in must and exp["k"] != must[jd]["k"]:
            violations.append(
                f"{jd}: expected 의 k={exp['k']} 와 must_haves 의 k={must[jd]['k']} 가 다르다")
        # `expected_fewer_than_k` 도 실측과 맞아야 한다
        if jd in must:
            actual_fewer = must[jd]["expected_qualified"] < must[jd]["k"]
            if exp.get("expected_fewer_than_k") != actual_fewer:
                violations.append(
                    f"{jd}: expected_fewer_than_k={exp.get('expected_fewer_than_k')} 인데 "
                    f"실측은 {must[jd]['expected_qualified']} < {must[jd]['k']} = {actual_fewer}")

        print(f"  {'  ' if not missing else 'X '} {jd:22} 언급 {len(named):2}명  "
              f"없는 id {sorted(missing) or '없음'}")

    if violations:
        print(f"\n위반 {len(violations)}건")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("\n위반 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
