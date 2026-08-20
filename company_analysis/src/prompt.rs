//! 시스템 인스트럭션과 프리셋.
//!
//! 여기 담는 것은 **정책**이지 데이터 지식이 아니다. 스키마의 생김새와 함정은
//! `data/CATALOG.md`에 있고, 에이전트가 그걸 읽어내는지가 평가 대상이다.
//! 함정의 답을 인스트럭션에 미리 적으면 예제가 증명하려는 것이 사라진다.

use std::fmt;

pub struct Paths<'a> {
    pub data: &'a str,
    pub workspace: &'a str,
    pub artifacts: &'a str,
}

/// 대표 질문 4종. 내부적으로는 잘 쓰인 task 문장 + 리포트 골격이다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Preset {
    CompanyProfile,
    SupplyChainRisk,
    DueDiligence,
    WatchlistMonitor,
}

impl Preset {
    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "company-profile" => Self::CompanyProfile,
            "supply-chain-risk" => Self::SupplyChainRisk,
            "due-diligence" => Self::DueDiligence,
            "watchlist-monitor" => Self::WatchlistMonitor,
            _ => return None,
        })
    }

    pub const ALL: [&'static str; 4] = [
        "company-profile",
        "supply-chain-risk",
        "due-diligence",
        "watchlist-monitor",
    ];

    pub fn slug(self) -> &'static str {
        match self {
            Self::CompanyProfile => "company-profile",
            Self::SupplyChainRisk => "supply-chain-risk",
            Self::DueDiligence => "due-diligence",
            Self::WatchlistMonitor => "watchlist-monitor",
        }
    }

    /// 대상 기업을 받아 task 문장을 만든다.
    pub fn task(self, company: &str) -> String {
        let company = &subject(company);
        match self {
            Self::CompanyProfile => format!(
                "{company}의 최근 실적과 사업 구조를 분석해줘. 지배구조와 주요 거래처를 포함해서."
            ),
            Self::SupplyChainRisk => format!(
                "{company}의 공급망을 n차까지 전개해서 제재·지정학 리스크를 찾아줘. \
                 집중도(단일 공급처·국가 편중)도 함께 봐줘."
            ),
            Self::DueDiligence => format!(
                "{company}와 거래하기 전에 알아야 할 것을 조사해줘. \
                 실체 확인, 지분·실소유 구조, 제재·소송 이력, 재무 건전성, 관계사 네트워크."
            ),
            Self::WatchlistMonitor => {
                "watchlist.csv의 모든 대상에 대해 직전 실행 이후의 변화를 요약해줘. \
                 변화가 없는 항목은 한 줄로만 적어줘."
                    .to_string()
            }
        }
    }

    /// 리포트 본문 구성. 요약·데이터 한계·다음 단계는 공통이라 여기 없다.
    fn body_sections(self) -> &'static [&'static str] {
        match self {
            Self::CompanyProfile => &[
                "개요와 지배구조",
                "재무 추이",
                "사업·제품",
                "주요 거래처",
                "강점과 약점",
            ],
            Self::SupplyChainRisk => &[
                "n차 협력사 전개",
                "집중도 (단일 공급처·국가 편중)",
                "제재·지정학 노출",
                "대체 공급처 후보",
                "시나리오별 영향",
            ],
            Self::DueDiligence => &[
                "실체 확인",
                "지분·실소유 구조",
                "제재·소송·사고 이력",
                "재무 건전성",
                "관계사 네트워크",
                "레드 플래그",
            ],
            Self::WatchlistMonitor => &[
                "변화가 있는 대상 (상세)",
                "변화가 없는 대상 (각 한 줄)",
                "신규 리스크",
            ],
        }
    }
}

/// `--company` 값을 task 문장에 넣을 형태로 만든다.
///
/// `company_id`를 그대로 넣으면 상호처럼 읽혀서, 에이전트가 이름으로 개체를 찾다가
/// 동명이인 경고에 걸린다. 키로 준 것임을 밝혀 그 단계를 건너뛰게 한다.
fn subject(company: &str) -> String {
    if looks_like_company_id(company) {
        format!("`company_id`가 `{company}`인 기업")
    } else {
        company.to_string()
    }
}

/// `kr-hanul-materials` 꼴 — 소문자 국가코드 두 자 + 하이픈으로 이어진 소문자·숫자.
///
/// 상호는 여기에 걸리지 않는다. 한글은 물론이고 영문 상호도 공백이나 대문자를 쓴다.
/// 걸려도 해는 없다 — 에이전트가 그 문자열로 개체를 찾는 것은 마찬가지다.
fn looks_like_company_id(s: &str) -> bool {
    let mut parts = s.split('-');
    let country = parts.next().unwrap_or("");
    country.len() == 2
        && country.chars().all(|c| c.is_ascii_lowercase())
        && parts.clone().count() >= 1
        && parts.all(|p| !p.is_empty() && p.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit()))
}

impl fmt::Display for Preset {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.slug())
    }
}

/// 시스템 인스트럭션.
pub fn instruction(paths: &Paths<'_>, preset: Option<Preset>, run_slug: &str) -> String {
    let Paths {
        data,
        workspace,
        artifacts,
    } = paths;

    let mut s = format!(
        "\
너는 기업정보 데이터 레이크를 조사해 근거와 함께 답하는 분석가다.

# 환경

- `{data}/` — 조사 대상. **읽기 전용이다. 절대 수정·삭제하지 않는다.**
- `{workspace}/{run_slug}/` — 중간 계산물. 자유롭게 써도 된다.
- `{artifacts}/{run_slug}/` — 최종 산출물. 여기와 workspace 밖으로는 쓰지 않는다.

# 시작

**먼저 `{data}/CATALOG.md`를 읽어라.** 데이터가 어떻게 생겼는지, 조인 키가 무엇인지,
어떤 함정이 있는지가 거기 있다. 읽지 않고 짐작으로 쿼리를 짜면 거의 틀린다.
그 다음 `{data}/registry/company_index.csv`가 원천들을 잇는 다리다.

계산은 `python_repl`로 한다. 표준 라이브러리(`csv`, `json`, `xml`)만으로 완주할 수
있게 데이터가 만들어져 있다. duckdb/pandas는 있으면 써도 되지만 없어도 된다.
파일 탐색과 확인은 `read`/`glob`/`grep`/`shell`을 쓴다.

# 진행 방식

**산출물을 마지막에 몰아 쓰지 않는다.** 조사를 다 끝낸 뒤에 리포트를 쓰려 하면
그 전에 턴이 소진되고 아무것도 남지 않는다.

- 첫 쿼리를 돌리기 전에 `report.md`의 뼈대(제목과 빈 섹션)를 먼저 써둔다.
- 섹션 하나의 근거가 확정될 때마다 그 섹션을 `edit`으로 채운다. 다음 섹션으로
  넘어가기 전에 채운다.
- `evidence.md`는 근거를 확인한 그 자리에서 한 줄씩 덧붙인다.
- `findings.json`은 마지막에 한 번 쓴다. 형식이 고정이라 부분 갱신이 어렵다.

**쓰겠다고 말만 하고 턴을 끝내지 않는다.** `이제 리포트를 작성한다`고 적을
것이면 같은 턴에서 `write`/`edit`을 호출한다. 툴을 부르지 않고 턴을 끝내도 되는
때는 산출물이 전부 디스크에 있고 할 말이 최종 답변뿐일 때다.

**막히면 막힌 채로 남긴다.** 어떤 계산이 안 되면 그 사실을 `report.md`의
데이터 한계에 적고 다음으로 넘어간다. 하나에 매달려 전체를 못 끝내지 않는다.

# 규칙

**근거.** 리포트의 모든 수치에 출처를 단다 — 파일 경로와 필터 조건, 또는 실행한
쿼리 파일명. 근거를 댈 수 없는 문장은 쓰지 않는다.

**없으면 없다고 쓴다.** 데이터에 없는 기업·거래·수치를 지어내지 않는다. 일반 상식으로
빈칸을 채우지 않는다. 추정할 때는 추정임을 밝히고 계산 과정을 남긴다.

**단정하지 않는다.** 이름이 비슷하다는 이유로 동일 개체라고 결론짓지 않는다.
제재 명단 대조는 이름 유사도에 기반하므로 후보 제시까지만 하고
`가능성 있는 일치 — 확인 필요`로 표기한다. 오탐의 비용이 큰 영역이다.

**모호하면 되묻는다.** 대상 기업 후보가 둘 이상이면 임의로 고르지 않는다.
국가·업종·설립연도를 제시해 확인을 요청하거나, 리포트 상단에 모호성을 명시한다.

**기준을 밝힌다.** 서로 다른 기준일·회계기준·통화의 값을 한 표에 섞지 않는다.
어느 기준으로 계산했는지 항상 적는다.

**검증한다.** 핵심 수치는 가능하면 다른 경로로 한 번 더 확인한다.
두 경로가 어긋나면 어긋난다는 사실 자체를 보고한다.

**점수를 낸다면 산식을 노출한다.** 가중치와 계산 과정 없이 숫자만 제시하지 않는다.

# 산출물

`{artifacts}/{run_slug}/` 아래에 쓴다.

- `report.md` — 사람이 읽는 리포트
- `evidence.md` — 주장 ↔ 근거(파일/쿼리) 대응표
- `findings.json` — 기계가 읽는 결과
- `queries/` — 실행한 쿼리를 파일로 남긴다 (`01-*.py` 형식)

`report.md`의 골격:

1. **요약** — 질문에 대한 3~5줄 답변. 여기서 결론이 끝나야 한다
"
    );

    if let Some(p) = preset {
        s.push_str("2. **핵심 발견** — 항목별로 사실 + 근거 + 신뢰도\n");
        s.push_str("3. **분석 본문**\n");
        for (i, sec) in p.body_sections().iter().enumerate() {
            s.push_str(&format!("   {}. {}\n", i + 1, sec));
        }
        s.push_str(
            "4. **데이터 한계** — 커버리지 구멍, 오래된 기준일, 낮은 신뢰도, 미해소 모호성\n\
             5. **다음 단계** — 사람이 확인해야 할 것, 추가로 필요한 데이터\n",
        );
    } else {
        s.push_str(
            "2. **핵심 발견** — 항목별로 사실 + 근거 + 신뢰도\n\
             3. **분석 본문** — 질문에 맞게 구성한다\n\
             4. **데이터 한계** — 커버리지 구멍, 오래된 기준일, 낮은 신뢰도, 미해소 모호성\n\
             5. **다음 단계** — 사람이 확인해야 할 것, 추가로 필요한 데이터\n",
        );
    }

    s.push_str(
        "\n`findings.json` 스키마는 고정이다 — 실행 간 비교(diff)에 쓰인다.\n\
         `{ \"run_id\", \"task\", \"entities\": [], \
         \"findings\": [{ \"severity\", \"statement\", \"evidence\": [], \"confidence\" }], \
         \"data_gaps\": [] }`\n",
    );

    if preset == Some(Preset::WatchlistMonitor) {
        s.push_str(
            "\n이번 실행은 **변화만** 보고한다. 직전 `findings.json`이 주어지면 그것과 비교해,\n\
             달라진 것을 상세히 쓰고 달라지지 않은 것은 한 줄로 처리한다.\n\
             매번 전체를 다시 서술하지 않는 것이 요구사항이다.\n",
        );
    }

    s
}

#[cfg(test)]
mod tests {
    use super::*;

    fn paths() -> Paths<'static> {
        Paths {
            data: "./data",
            workspace: "./workspace",
            artifacts: "./artifacts",
        }
    }

    #[test]
    fn company_id_is_named_as_a_key_not_a_name() {
        for id in ["kr-hanul-materials", "us-northgate-cells", "cn-beifeng-lithium"] {
            assert!(looks_like_company_id(id), "{id}");
            let t = Preset::DueDiligence.task(id);
            assert!(t.contains("`company_id`가"), "{t}");
            assert!(t.contains(id), "{t}");
        }
    }

    #[test]
    fn a_trade_name_is_left_alone() {
        for name in ["한울소재", "Acme Materials", "Acme-Corp", "kr", "kr-", "-kr-x", "삼성전자"] {
            assert!(!looks_like_company_id(name), "{name}");
        }
        let t = Preset::DueDiligence.task("한울소재");
        assert!(t.starts_with("한울소재"), "{t}");
        assert!(!t.contains("company_id"), "{t}");
    }

    #[test]
    fn presets_round_trip() {
        for slug in Preset::ALL {
            let p = Preset::parse(slug).expect(slug);
            assert_eq!(p.slug(), slug);
            assert!(!p.task("한울소재").is_empty());
        }
        assert!(Preset::parse("nope").is_none());
    }

    #[test]
    fn instruction_carries_policy_not_answers() {
        let s = instruction(&paths(), Some(Preset::SupplyChainRisk), "run-1");
        // 경로와 경계
        assert!(s.contains("./data/CATALOG.md"));
        assert!(s.contains("./artifacts/run-1/"));
        assert!(s.contains("읽기 전용"));
        // 정책
        assert!(s.contains("가능성 있는 일치 — 확인 필요"));
        assert!(s.contains("되묻는다"));
        // 프리셋 본문
        assert!(s.contains("n차 협력사 전개"));
        // 증분 작성 — 마지막에 몰아 쓰다 턴이 소진되는 실패를 막는 부분
        assert!(s.contains("몰아 쓰지 않는다"));
        assert!(s.contains("말만 하고 턴을 끝내지 않는다"));

        // 함정의 답이 새어 나가면 안 된다 — CATALOG를 읽어야만 알 수 있어야 한다
        for leak in ["CFS", "OFS", "ord", "당기순이익", "Beifang", "대진화학", "bizr_no"] {
            assert!(!s.contains(leak), "인스트럭션이 함정의 답을 흘린다: {leak}");
        }
    }

    #[test]
    fn watchlist_asks_for_a_diff() {
        let s = instruction(&paths(), Some(Preset::WatchlistMonitor), "run-1");
        assert!(s.contains("변화만"));
        let other = instruction(&paths(), Some(Preset::CompanyProfile), "run-1");
        assert!(!other.contains("변화만"));
    }
}


