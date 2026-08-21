"""`TRANSCRIPT.md` 의 SQL 이 실제로 도는지.

**예제의 대표 화면이 존재하지 않는 컬럼을 가르치면 안 된다.** 최종 리뷰가 두 건을
찾았다 — `candidate_tenure` 에 없는 `naive_years`·`city` 를 쓰는 쿼리, 그리고
`LIMIT 5` 를 걸고 `68 rows` 라고 적은 화면(지침이 바로 그 함정을 경고한다).

손으로 읽어서는 안 잡힌다. 돌려 봐야 한다.
"""

import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent.parent
DB = HERE / "data" / "headhunter.db"

# 화면은 `│ ` 로 SQL 을 들여쓴다. 연속된 줄이 한 쿼리다.
SQL_LINE = re.compile(r"^│ (.*)$", re.M)


def queries(text: str) -> list[str]:
    """화면의 SQL 블록들. `┌ sqlite` 로 열고 `└` 로 닫힌다.

    `│` 줄만 모으되 **`┌` 를 만나면 새 쿼리로 끊는다.** 그것 없이 공백줄만으로
    끊으면 인접한 두 블록이 한 덩어리가 되고, 앞 쿼리의 `LIMIT` 이 뒤 쿼리의 것으로
    보고된다 — 실제로 그렇게 오탐 셋이 났다.
    """
    out, cur = [], []
    for line in text.splitlines():
        if line.startswith("┌"):
            if cur:
                out.append("\n".join(cur))
            cur = []
            continue
        m = re.match(r"^│ ?(.*)$", line)
        if m:
            cur.append(m.group(1))
        elif cur:
            out.append("\n".join(cur))
            cur = []
    if cur:
        out.append("\n".join(cur))
    return out


def main() -> int:
    con = sqlite3.connect(DB)
    text = (HERE / "TRANSCRIPT.md").read_text()
    bad = []
    n = 0
    for q in queries(text):
        # 도구 플래그는 SQL 이 아니다. 떼고 돌린다.
        sql = re.sub(r"--limit \d+", "", q).strip().rstrip(";")
        if not sql.upper().startswith(("SELECT", "PRAGMA", "WITH")):
            continue
        # `…52 ids…` 같은 생략 표기가 있는 화면은 그대로 돌 수 없다. 생략 자체는
        # 정당하므로(52개 id 를 화면에 늘어놓을 수 없다) 자리 표시자를 채워 돌린다.
        if "…" in sql or "..." in sql:
            sql = re.sub(r"…[^…]*…|\.\.\.[^.]*\.\.\.", "''", sql)
        n += 1
        try:
            con.execute(sql).fetchall()
        except sqlite3.Error as e:
            bad.append((sql.splitlines()[0][:70], str(e)))

    print(f"TRANSCRIPT 의 SQL {n}개 실행")
    if bad:
        print(f"\n돌지 않는 쿼리 {len(bad)}건")
        for head, err in bad:
            print(f"  X {head}…")
            print(f"      {err}")
        return 1
    print("전부 정상")

    # SQL 안의 `LIMIT` 은 도구의 절단 안내를 침묵시킨다 — 지침이 경고하는 동작이다.
    # 화면이 그것을 시범 보이면 안 된다. 다만 `GROUP BY … LIMIT` 처럼 집계 상위 N 을
    # 보는 것은 정당하므로, **행 수를 함께 보고하는 화면**만 문제 삼는다.
    # 집계의 상위 N(`GROUP BY … ORDER BY … LIMIT`)은 정당하다 — 분포를 보는 것이지
    # 후보 목록을 자르는 것이 아니다. 문제는 **후보 행을 자르면서 총원을 말하는** 쿼리다.
    lit = []
    for q in queries(text):
        # **도구 플래그 `--limit` 을 먼저 떼야 한다.** 안 떼면 그 안의 `limit` 이
        # SQL 키워드로 읽혀 올바른 화면이 위반으로 잡힌다 — 실제로 그렇게 오탐 둘이 났다.
        u = re.sub(r"--limit\s+\d+", "", q, flags=re.I).upper()
        if not re.search(r"\bLIMIT\s+\d+", u):
            continue
        if "GROUP BY" in u:
            continue
        lit.append(q)
    if lit:
        print(f"\n주의: SQL 내부 LIMIT 을 쓰는 화면 {len(lit)}건 — `--limit` 이 맞다")
        for q in lit:
            print(f"  · {q.splitlines()[0][:70]}…")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
