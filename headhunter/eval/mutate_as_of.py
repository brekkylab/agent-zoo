"""AS_OF 검사의 변이 실험 — 실제 실수의 모양은 '한쪽만' 바뀌는 것이다.

**변이가 실제로 적용됐는지 먼저 확인한다.** 안 그러면 원본을 돌려 놓고
"조용히 통과" 라고 보고하게 된다 — 실제로 그렇게 한 번 틀렸다.
"""
import subprocess
import sys
from pathlib import Path
H = Path(__file__).resolve().parent.parent
V = H / "sql/views.sql"
PY_ = H.parent / "_datagen" / ".venv" / "bin" / "python"
orig = V.read_text()
SQL_LINE = "COALESCE(end_year*12 + COALESCE(end_month,1), 2026*12+8)"
assert SQL_LINE in orig, "기준 문자열이 views.sql 에 없다"

def run(label, mutated):
    if mutated == orig:
        print(f"  [{label}] **변이 실패 — 원본과 같다**")
        return
    V.write_text(mutated)
    r = subprocess.run([str(PY_), "sql/load.py"], cwd=H, capture_output=True, text=True)
    V.write_text(orig)
    caught = r.returncode != 0
    print(f"  [{label}] {'잡음' if caught else '**조용히 통과**'}  exit={r.returncode}")
    if caught:
        print(f"      {(r.stdout + r.stderr).strip().splitlines()[-1][:95]}")

# 실제 실수 1: SQL 만 고치고 주석은 그대로 — 데이터가 어긋난다. 잡아야 한다.
run("SQL 만 2027 (주석은 2026)", orig.replace(SQL_LINE, SQL_LINE.replace("2026*12+8", "2027*12+8")))
# 실제 실수 2: 월만 한 칸 — 현직자 전원이 1개월 어긋난다. 잡아야 한다.
run("SQL 만 2026*12+9", orig.replace(SQL_LINE, SQL_LINE.replace("2026*12+8", "2026*12+9")))
# 실제 실수 3: 리터럴을 미리 계산한 값으로 — 읽기는 같지만 검사는 찾지 못한다. 잡아야 한다.
run("SQL 을 24320 으로 (주석에만 리터럴)", orig.replace(SQL_LINE, SQL_LINE.replace("2026*12+8", "24320")))
# 주석만 고치는 것은 데이터에 영향이 없다. 통과가 맞다.
run("주석만 2027 (SQL 은 2026)", orig.replace("-- `2026*12+8` 은", "-- `2027*12+8` 은"))

ok = V.read_text() == orig
print(f"\n  복원 확인: {'OK' if ok else '**깨짐 — views.sql 을 git 에서 되돌려라**'}")
sys.exit(0 if ok else 1)
