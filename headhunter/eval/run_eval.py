"""에이전트 산출물을 채점한다. spec §6.2.

**완전 자동 채점은 목표가 아니다.** 자동으로 잡히는 실패와 **사람 확인 항목 리스트**를
출력한다. 개인화 문장이 자연스러운가 같은 것은 사람이 봐야 한다.

    run_eval.py --check          JD 의 적격자 수·기대 랭킹이 데이터와 맞는지
    run_eval.py --score <dir>    산출물 채점. <dir> 은 `artifacts/<role-slug>`

`--check` 는 에이전트를 돌리기 **전에** 쓴다. 채점 기준이 데이터와 어긋나 있으면
채점 자체가 무의미하다.
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
ID = re.compile(r"urn:li:person:\w+")

sys.path.insert(0, str(HERE))
from check_expected import main as check_expected  # noqa: E402
from check_must_haves import main as check_must_haves  # noqa: E402


def check() -> int:
    """채점 기준이 데이터와 맞는지. 두 검사를 이어 돌린다.

    두 검사가 별도 파일인 이유는 각자 혼자서도 의미가 있기 때문이다 —
    `check_must_haves` 는 JD 를 고칠 때, `check_expected` 는 정답을 고칠 때 쓴다.
    """
    print("must-have 조건이 내는 수:")
    a = check_must_haves()
    print("\n기대 랭킹이 가리키는 사람:")
    b = check_expected()
    return a or b


# 지침이 요구하는 마커. 이것이 1순위다.
PICKS_HEADING = re.compile(r"^(#{1,6})\s*(?:picks?|선정|고른)\b.*$", re.M | re.I)


def _picks_list(text: str) -> str:
    """`## Picks` 절의 본문. 없으면 빈 문자열.

    지침이 이 절을 요구하는 이유는 **선정 구역 안에서도 다른 사람을 인용하는 것이
    정당하기 때문**이다. 실제 실행에서 에이전트가 3번 후보를 설명하며 동명이인 확인차
    다른 id 를 적었고, 구역 기준 집계가 그것을 네 번째 선정으로 셌다.

    다음 헤딩까지를 절의 본문으로 본다.
    """
    m = PICKS_HEADING.search(text)
    if not m:
        return ""
    # **같은 레벨 이상의 헤딩에서만 끊는다.** 후보마다 `###` 하위 절을 두는 것이
    # 자연스럽고, 어떤 헤딩에서든 끊으면 첫 후보 앞에서 잘려 목록이 비어 버린다.
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


REJECTED_MARKER = re.compile(r"^<!--\s*rejected\s*-->\s*$", re.M | re.I)

# 마커가 없을 때의 보조. **이것에 의존하지 않는다.**
REJECTION_HEADING = re.compile(
    r"^#{1,6}\s*.*(버린|뺀|뺐|제외|않은|탈락|보내지|rejected?|excluded?"
    r"|not\s+contact|why\s+not|걸러)",
    re.M | re.I,
)


def _selection_part(text: str) -> tuple[str, bool]:
    """숏리스트에서 **고른 사람** 구역만. `(본문, 마커를_찾았는가)`.

    거절 구역을 남겨 두면 그 안에 적힌 함정이 "상위 k 에 있다" 로 집계된다. 그러면
    거절 사유를 성실히 쓴 산출물이 더 나쁜 점수를 받는다 — 지침이 요구한 행동에
    벌점을 주는 채점기가 된다.

    **헤딩 문구를 정규식으로 맞히려는 시도는 실패한다.** 한국어는 활용이 있고
    (뺀/뺐/빼는) 영어는 표현이 무한하다. 첫 판이 `빼` 를 넣고 `뺀` 을 놓쳐서, 이
    저장소가 직접 쓴 숏리스트에서조차 구역을 못 잘랐다.

    그래서 지침이 `<!-- rejected -->` 한 줄을 요구하고 이 함수는 그것을 본다.
    문서 형식을 알아맞히는 대신 형식을 정하는 쪽이다. 마커가 없으면 헤딩 휴리스틱으로
    떨어지되, 그 사실을 호출자에게 알려 사람 확인 항목으로 낸다 — 조용히 추측하면
    채점이 틀린 줄도 모른다.
    """
    m = REJECTED_MARKER.search(text)
    if m:
        return text[: m.start()], True
    m = REJECTION_HEADING.search(text)
    return (text[: m.start()] if m else text), False


def score(con: sqlite3.Connection, artifacts: Path) -> tuple[list[str], list[str]]:
    """산출물을 채점한다. 자동 실패와 사람 확인 항목을 나눠 돌려준다."""
    auto: list[str] = []
    human: list[str] = []

    truth = {t["id"]: t for t in json.loads((DATA / "ground_truth.json").read_text())}
    in_db = {r[0] for r in con.execute("SELECT id FROM candidates")}
    lang = dict(con.execute("SELECT id, profile_language FROM candidates"))
    name_of = dict(con.execute("SELECT id, name FROM candidate_brief"))

    jd = artifacts.name
    expected_path = HERE / "expected" / f"{jd}.json"
    if not expected_path.exists():
        auto.append(f"{jd}: eval/expected/{jd}.json 이 없다 — 채점 기준이 없다")
        return auto, human
    exp = json.loads(expected_path.read_text())

    shortlist = artifacts / "00-shortlist.md"
    if not shortlist.exists():
        auto.append(f"{artifacts}/00-shortlist.md 가 없다")
        return auto, human

    files = sorted(artifacts.glob("*.md"))
    text_of = {p.name: p.read_text() for p in files}

    # ── 언급된 id 가 실재하는가 ───────────────────────────────────────
    for name, text in text_of.items():
        for cited in sorted(set(ID.findall(text))):
            if cited not in in_db:
                auto.append(f"{name}: 존재하지 않는 id {cited}")

    # **선정 구역만 본다.** 숏리스트는 고른 사람과 버린 사람을 함께 적는다 — 지침이
    # 그것을 요구한다("Name the people you rejected and why"). 파일 전체에서 이름을
    # 찾으면 거절 사유에 적힌 함정이 "상위 k 에 있다" 로 읽히고, **거절 사유를 잘
    # 적을수록 점수가 나빠진다.** 채점이 지침과 싸우는 상태다.
    #
    # 그래서 거절 구역을 잘라낸다. 표제가 무엇이든 "버린/제외/않은/rejected/not" 이
    # 들어간 헤딩 아래는 선정이 아니다.
    body, marked = _selection_part(text_of.get("00-shortlist.md", ""))
    picks = _picks_list(text_of.get("00-shortlist.md", ""))
    if picks:
        # `## Picks` 목록이 있으면 그것이 정본이다. 선정 구역 안에서도 다른 사람을
        # 인용할 정당한 이유가 있으므로(동명이인 확인·비교), 구역만으로는 못 가른다.
        # 실제 실행이 그것으로 오탐을 냈다 — 에이전트가 3명을 골랐는데 4명으로 세어졌다.
        body = picks
    if not marked:
        human.append(
            "숏리스트에 `<!-- rejected -->` 마커가 없다 — 헤딩 문구로 선정/거절을 "
            "추측했다. 거절한 사람이 '상위 k 에 있다' 로 잘못 집계됐을 수 있으므로 "
            "아래 자동 실패를 사람이 한 번 확인한다")
    cited = set(ID.findall(body))
    # 이름 매칭은 **보조 경로**다. 지침이 전체 urn 을 요구하고(§Ranking rules), 그것이
    # 있으면 위 정규식이 전부 잡는다.
    #
    # 이름에 기대면 안 되는 이유가 실측으로 분명하다 — **600명 중 283명(47%)이
    # 동명이인**이고, 유일하지 않은 이름이 124종이다(`Rowan Thorne` 6명,
    # `Kai Lockhart` 4명). 계획된 함정·대조군 28명 중 12명의 이름이 유일하지 않다.
    #
    # 그래서 이름만 적힌 산출물에서는 세 검사가 조용히 죽는다: `must_not_appear` 가
    # 발화하지 않고, `duplicate-profile` 쌍은 이름이 `Kai Lockhart` 라 둘 다 인식되지
    # 않으며, 대조군 넷은 항상 "없다" 로 오탐된다.
    by_name: dict[str, list[str]] = {}
    for i, n in name_of.items():
        by_name.setdefault(n, []).append(i)
    named_ambiguous = []
    for n, ids in by_name.items():
        if len(n) >= 3 and n in body:
            if len(ids) == 1:
                cited.add(ids[0])
            else:
                named_ambiguous.append(n)
    # **이름이 나온 것 자체는 문제가 아니다.** 산문이 "Nova Vance 는 …" 이라고 쓰는 것은
    # 자연스럽고, 같은 이름을 가진 사람 중 하나의 id 가 이미 인용돼 있으면 모호하지 않다.
    # 걸러낼 것은 **id 없이 이름으로만 등장하는 사람**이다.
    named_ambiguous = [n for n in named_ambiguous if not (set(by_name[n]) & cited)]
    if named_ambiguous:
        # **`same-name` 함정이라 부르지 않는다.** 심어 둔 그 함정은 `서연 강` 하나이고,
        # 124개 충돌 중 하나다. 나머지는 배경 인구의 우연한 이름 재사용이다.
        auto.append(
            f"숏리스트가 {len(named_ambiguous)}명을 id 없이 이름으로만 가리킨다 "
            f"({', '.join(sorted(named_ambiguous)[:3])}…) — 이 이름들은 여러 사람이 "
            f"공유하므로 누구를 말하는지 정해지지 않는다. 지침이 전체 "
            f"`urn:li:person:…` 을 요구한다")

    # id 를 하나도 안 썼으면 아래 검사 전부가 무의미하다. 조용히 통과시키지 않는다.
    if not cited and not exp.get("expected_fewer_than_k"):
        auto.append(
            "숏리스트에 `urn:li:person:…` 이 하나도 없다 — must_not_appear·중복 탐지·"
            "대조군 검사가 전부 무동작이 된다")

    # **여기서 early return 하지 않는다.** `blockchain-solidity` 는 아무도 내지 않는
    # 것이 정답이고, 그 산출물이 도달하는 상태가 정확히 `not cited` 다. 이 자리에서
    # 돌려보내면 정답이 자동 실패를 받고 그 JD 의 채점 기준 네 줄이 한 줄도 안 나온다 —
    # 채점기가 `expected/blockchain-solidity.json` 과 정반대로 동작한다.
    #
    # 아래 `expected_fewer_than_k` 분기가 0명을 옳게 처리하므로, 판정을 거기 맡긴다.
    if not cited and not exp.get("expected_fewer_than_k"):
        auto.append("00-shortlist.md 가 어떤 후보도 식별하지 않는다")
        return auto, human

    # ── 나타나면 안 되는 사람 ─────────────────────────────────────────
    for entry in exp.get("must_not_appear", []):
        if entry["id"] in cited:
            trap = entry.get("trap") or "clear-miss"
            auto.append(
                f"상위 k 에 {name_of.get(entry['id'], entry['id'])} 가 있다 "
                f"[{trap}] — {entry['why'][:70]}")

    # ── 대조군이 살아남았는가 ─────────────────────────────────────────
    #
    # 이것이 "정답" 과 "이유가 틀린 정답" 을 가른다. 대조군은 함정과 한 축만 다르고 그
    # 축이 통과하는 쪽이므로, 소거법을 쓰면 함정과 함께 버려진다. 다만 **버린 것이
    # 반드시 오답은 아니다** — 52명 중 3명을 고르는 JD 에서 대조군이 4등일 수 있다.
    # 그래서 자동 실패가 아니라 사람 확인으로 낸다.
    for entry in exp.get("controls_that_must_not_be_rejected", []):
        if entry["id"] not in cited:
            human.append(
                f"대조군 {name_of.get(entry['id'], entry['id'])} "
                f"({entry['control_for']} 의 대조군)가 숏리스트에 없다 — 순위에서 밀린 "
                f"것인지 '수상하다' 고 버린 것인지 거절 사유를 읽어야 한다")

    # ── 중복 프로필: 같은 사람이 둘 ──────────────────────────────────
    #
    # **`pair_with` 를 그냥 쓰면 안 된다.** 세 함정이 그 필드를 공유하는데 방향이 다르다:
    #
    #   duplicate-profile  두 기록이 한 사람 — 둘 다 있으면 **실패**
    #   same-name          같은 이름이 두 사람 — 둘 다 있어도 **정상**
    #   rank-inversion-pair 다른 두 사람 — 둘 다 있어도 정상
    #
    # 계획의 이전 판은 `truth[i].get("duplicate_of")` 를 봤는데 그 필드는 존재하지
    # 않는다. 항상 None 이므로 이 검사가 영원히 아무것도 하지 않는다 — fail-open 이다.
    for i in sorted(cited):
        t = truth.get(i)
        if not t or t.get("trap") != "duplicate-profile":
            continue
        other = t.get("pair_with")
        if other and other in cited:
            auto.append(
                f"상위 k 에 같은 사람이 둘 있다: {i[-8:]} 와 {other[-8:]} "
                f"({name_of.get(i)}) — duplicate-profile 함정을 놓쳤다")

    # ── k 보다 적게 냈는가 ────────────────────────────────────────────
    k = exp["k"]
    if exp.get("expected_fewer_than_k"):
        expected_n = len(exp.get("acceptable_top_k", []))
        if len(cited) >= k:
            auto.append(
                f"적격자가 k({k})보다 적은 JD 인데 {len(cited)}명을 냈다 — "
                f"{exp.get('why_fewer', '')}")
        elif not cited and expected_n == 0:
            # 적격자가 0명인 JD. 아무도 안 낸 것이 정답이므로 자동 실패가 아니다.
            human.append(
                "아무도 내지 않았다 — 이 JD 는 그것이 정답이다. **무엇을 찾아봤는지**가 "
                "적혀 있는지 확인한다. 검색을 하지 않고 없다고 말한 것과 구별되지 않으면 "
                "합격이 아니다")
        else:
            human.append(
                f"{len(cited)}명을 냈다(k={k}). **왜 {k}명이 안 되는지** 숏리스트에 "
                f"적혀 있는지 확인한다")
    elif len(cited) > k:
        auto.append(f"상위 {k} 를 요구했는데 {len(cited)}명을 냈다")

    # ── 콜드메일의 언어 ──────────────────────────────────────────────
    #
    # 자동으로 볼 수 있는 것은 "한글이 있는가" 까지다. 한국어 프로필에 영어 메일을
    # 보냈으면 잡히지만, 어색한 한국어는 사람이 봐야 한다.
    hangul = re.compile(r"[가-힣]")
    for name, text in text_of.items():
        if name == "00-shortlist.md":
            continue
        ids = [i for i in ID.findall(text) if i in lang]
        if not ids:
            # id 없이 이름만 쓴 메일. 사람 확인으로 넘긴다.
            human.append(f"{name}: 후보 id 가 없어 언어 대조를 자동으로 못 한다")
            continue
        want = lang[ids[0]]
        has_ko = bool(hangul.search(text))
        if want == "ko" and not has_ko:
            auto.append(f"{name}: 후보의 profile_language 가 ko 인데 한국어가 아니다")
        if want == "en" and has_ko:
            human.append(
                f"{name}: profile_language 가 en 인데 한글이 있다 — 데이터에 있던 "
                f"고유명사(`러스트`·`서버 개발자`)면 옳고, 창작이면 오류다")

    # ── 함정별 사람 확인 항목 ────────────────────────────────────────
    for entry in exp.get("traps_that_must_be_caught", []):
        i = entry.get("id")
        seen = " (숏리스트에 있음)" if i in cited else ""
        human.append(f"[{entry['trap']}]{seen} {entry['expected']}")

    for note in exp.get("scoring_notes", []):
        human.append(f"[채점 기준] {note}")

    return auto, human


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="채점 기준이 데이터와 맞는지 (에이전트를 돌리기 전에)")
    ap.add_argument("--score", type=Path, metavar="DIR",
                    help="산출물 채점. artifacts/<role-slug>")
    args = ap.parse_args()

    if args.check:
        return check()
    if not args.score:
        ap.print_help()
        return 2

    con = sqlite3.connect(DATA / "headhunter.db")
    auto, human = score(con, args.score)

    print(f"채점: {args.score}\n")
    if auto:
        print(f"자동 실패 {len(auto)}건")
        for a in auto:
            print(f"  X {a}")
    else:
        print("자동 실패 없음")

    print(f"\n사람이 확인할 것 {len(human)}건")
    for h in human:
        print(f"  · {h}")

    return 1 if auto else 0


if __name__ == "__main__":
    sys.exit(main())
