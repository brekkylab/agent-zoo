"""JSON 을 SQLite 로 적재한다.

# 왜 파이썬인가

이 스크립트는 예제가 돌기 전에 한 번 도는 준비 단계다. 에이전트도 ailoy 도 이것을 부르지
않는다. 계획 B 의 생성기가 이미 파이썬이고 `AS_OF` 가 그쪽에 있으므로, 같은 언어로 두면
그 상수를 import 로 가져올 수 있다.

# journal_mode 를 여기서 정한다

`cortex-execs/sqlite` 는 남의 DB 를 읽기 전용으로 열고 WAL 을 금한다. 그런데 journal mode
는 커넥션 속성이 아니라 **파일 헤더의 속성**이므로 읽는 쪽이 보장할 수 없다 — 만드는 쪽의
몫이다(계획 A 의 "C 계획이 책임져야 할 것" 2번). `DELETE` 로 명시한다.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
# `_datagen` 은 형제 디렉터리다. `AS_OF` 를 한 곳에서만 정의하려면 여기서 가져와야 한다.
sys.path.insert(0, str(HERE.parent.parent / "_datagen"))
from common.dates import AS_OF  # noqa: E402


def assert_as_of_matches() -> None:
    """`views.sql` 의 리터럴이 생성기의 `AS_OF` 와 같은지.

    **에러 없이 조용히 틀리는 지점이다.** `views.sql` 이 `2026*12+8` 로 현직의 끝을
    채우고 생성기 `dates.py` 가 같은 값을 쓴다. 어긋나면 함정 3(겸직 중첩)의 정답과
    VIEW 의 계산이 달라지는데 SQL 도 파이썬도 아무 불평을 하지 않는다.

    spec §2.2 가 "생성기가 템플릿에서 렌더링해 한 곳에서만 정의" 하라고 했으나, 렌더링을
    도입하면 `views.sql` 이 생성물이 되어 사람이 읽고 고치는 파일이 아니게 된다. 리터럴을
    두고 검사하는 쪽이 이 규모에서 낫다 — 검사가 렌더링과 같은 것을 보장하고, 파일은
    여전히 손으로 읽힌다.
    """
    expected = f"{AS_OF[0]}*12+{AS_OF[1]}"
    raw = (HERE / "views.sql").read_text()
    # **주석을 걷어내고 본다.** 같은 리터럴이 설명 주석에도 나오므로, 전체 텍스트에서
    # 찾으면 SQL 을 고치고 주석을 안 고쳤을 때(또는 그 반대) 검사가 주석으로 만족한다 —
    # fail-open 이다.
    #
    # 처음에 이 검사를 "깨뜨려 확인" 했는데도 놓쳤다. 변이가
    # `sed 's/2026\*12+8/2027*12+8/'` 이라 **주석과 SQL 을 동시에** 바꿨기 때문이다.
    # 실제 실수는 한쪽에서만 난다.
    code = re.sub(r"--.*", "", raw)
    if expected not in code:
        raise SystemExit(
            f"views.sql 의 SQL 에 {expected!r} 가 없다 — 생성기의 AS_OF={AS_OF} 와 "
            f"어긋난다. 함정 3 의 정답과 VIEW 의 계산이 조용히 달라진다"
        )
    # 현직의 끝을 채우는 그 자리인지까지 확인한다. 다른 곳에 우연히 같은 산술식이
    # 있어도 만족되면 안 된다.
    if not re.search(rf"COALESCE\([^)]*\)\s*,\s*{re.escape(expected)}\s*\)", code):
        raise SystemExit(
            f"views.sql 에 {expected!r} 가 있지만 현직 종료 시점을 채우는 "
            f"`COALESCE(..., {expected})` 자리가 아니다"
        )


def load(db_path: Path) -> None:
    candidates = json.loads((DATA / "candidates.json").read_text())
    narration_path = DATA / "narration.json"
    narration = json.loads(narration_path.read_text()) if narration_path.exists() else {}

    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    # WAL 이 아니어야 한다. 위 docstring 참조.
    con.execute("PRAGMA journal_mode = DELETE")
    con.executescript((HERE / "schema.sql").read_text())
    con.executescript((HERE / "views.sql").read_text())

    for c in candidates:
        prose = narration.get(c["id"], {})
        con.execute(
            "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                c["id"], c["first_name"], c["last_name"], c["headline"],
                prose.get("summary", c.get("summary", "")),
                c["city"], c["country"], c["industry"], c["job_function"],
                c["seniority"], c["profile_language"], int(c["open_to_work"]),
                c["connections_count"], c["last_updated_at"], c["public_profile_url"],
            ),
        )
        descriptions = prose.get("descriptions", [])
        for i, p in enumerate(c["positions"]):
            con.execute(
                "INSERT INTO positions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    c["id"], i, p["title"], p["company_name"], p["company_urn"],
                    p["company_size"], p["employment_type"], p["workplace_type"],
                    p["location"],
                    descriptions[i] if i < len(descriptions) else p.get("description", ""),
                    p["start_year"], p["start_month"],
                    p.get("end_year"), p.get("end_month"),
                ),
            )
        for s in c["skills"]:
            con.execute(
                "INSERT INTO skills VALUES (?,?,?)",
                (c["id"], s["name"], s["endorsement_count"]),
            )
        for e in c.get("educations", []):
            con.execute(
                "INSERT INTO educations VALUES (?,?,?,?,?,?)",
                (c["id"], e["school_name"], e["degree_name"], e["field_of_study"],
                 e["start_year"], e["end_year"]),
            )
        for t in c.get("certifications", []):
            con.execute(
                "INSERT INTO certifications VALUES (?,?,?)",
                (c["id"], t["name"], t["authority"]),
            )
        for lang in c.get("languages", []):
            con.execute(
                "INSERT INTO languages VALUES (?,?,?)",
                (c["id"], lang["name"], lang["proficiency"]),
            )
        for pref in c.get("open_to_work_prefs", []):
            con.execute(
                "INSERT INTO open_to_work_prefs VALUES (?,?,?,?,?,?)",
                (c["id"], pref["desired_title"], pref["location_type"],
                 pref["desired_location"], pref["start_date"], pref["employment_type"]),
            )
        for contact in c.get("contacts", []):
            con.execute(
                "INSERT INTO contacts VALUES (?,?,?)",
                (c["id"], contact["method"], contact["note"]),
            )

    # FTS5 는 정규화 테이블에서 채운다. 한 후보의 여러 행을 한 문서로 이어붙인다 —
    # `MATCH 'rust'` 가 스킬에 있든 헤드라인에 있든 그 사람을 찾아야 하기 때문이다.
    con.execute("""
        INSERT INTO candidate_fts (id, headline, summary, titles, descriptions, skill_names)
        SELECT c.id, c.headline, c.summary,
               (SELECT group_concat(title, ' ') FROM positions WHERE candidate_id = c.id),
               (SELECT group_concat(description, ' ') FROM positions WHERE candidate_id = c.id),
               (SELECT group_concat(name, ' ') FROM skills WHERE candidate_id = c.id)
        FROM candidates c
    """)
    con.commit()
    counts = {
        t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("candidates", "positions", "skills", "contacts", "candidate_fts")
    }
    con.close()
    print(f"wrote {db_path}")
    for t, n in counts.items():
        print(f"  {t:16} {n}")


def main() -> None:
    assert_as_of_matches()
    load(DATA / "headhunter.db")


if __name__ == "__main__":
    main()
