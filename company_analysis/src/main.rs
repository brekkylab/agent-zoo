//! 기업정보 데이터 레이크를 조사해 근거와 함께 리포트로 답하는 에이전트.
//!
//! ```sh
//! cargo run -p company_analysis -- --preset supply-chain-risk --company "한울소재"
//! cargo run -p company_analysis -- --task "한울소재의 중국 의존도를 2차 협력사까지 분석해줘"
//! ```

mod guard;
mod prompt;

use std::path::{Path, PathBuf};

use ailoy::{
    agent::AgentBuilder,
    console::Console,
    lang_model::get_lm_providers_mut,
    message::{Message, Part, Role, TokenUsage},
};
use anyhow::{Context, Result, bail};
use futures::StreamExt;

use crate::{
    guard::{DataFingerprint, WriteBoundary},
    prompt::{Paths, Preset},
};

const DEFAULT_MODEL: &str = "anthropic/claude-sonnet-5";

/// 명령은 호스트에서 직접 실행된다. `data/` 읽기 전용은 격리가 아니라
/// [`guard`]의 사후 검출로만 보장된다.
const CONSOLE_PROGRAM: &str = "cortex-local-console";

/// `build.rs`가 `cargo install`로 받아둔 콘솔 서버 경로.
const CONSOLE_INSTALLED: &str = env!("CORTEX_CONSOLE");

struct Args {
    task: Option<String>,
    preset: Option<Preset>,
    company: Option<String>,
    since: Option<PathBuf>,
    data: PathBuf,
    out: PathBuf,
    workspace: PathBuf,
    model: String,
}

fn parse_args() -> Result<Args> {
    let mut a = Args {
        task: None,
        preset: None,
        company: None,
        since: None,
        data: PathBuf::from("./data"),
        out: PathBuf::from("./artifacts"),
        workspace: PathBuf::from("./workspace"),
        model: DEFAULT_MODEL.to_string(),
    };
    let mut it = std::env::args().skip(1);
    while let Some(flag) = it.next() {
        let mut value = || {
            it.next()
                .ok_or_else(|| anyhow::anyhow!("{flag}에 값이 없다"))
        };
        match flag.as_str() {
            "--task" => a.task = Some(value()?),
            "--task-file" => {
                let p = value()?;
                a.task = Some(std::fs::read_to_string(&p).with_context(|| format!("읽기 {p}"))?);
            }
            "--preset" => {
                let v = value()?;
                a.preset = Some(Preset::parse(&v).ok_or_else(|| {
                    anyhow::anyhow!("알 수 없는 프리셋 '{v}' (가능: {})", Preset::ALL.join(", "))
                })?);
            }
            "--company" => a.company = Some(value()?),
            "--since" => a.since = Some(PathBuf::from(value()?)),
            "--data" => a.data = PathBuf::from(value()?),
            "--out" => a.out = PathBuf::from(value()?),
            "--workspace" => a.workspace = PathBuf::from(value()?),
            "--model" => a.model = value()?,
            "-h" | "--help" => {
                print_help();
                std::process::exit(0);
            }
            other => bail!("알 수 없는 인자 '{other}' (--help 참조)"),
        }
    }
    if a.task.is_none() && a.preset.is_none() {
        bail!("--task 또는 --preset 중 하나는 필요하다 (--help 참조)");
    }
    if a.preset.is_some_and(|p| p != Preset::WatchlistMonitor) && a.company.is_none() {
        bail!("이 프리셋에는 --company가 필요하다");
    }
    Ok(a)
}

fn print_help() {
    println!(
        "\
company_analysis — 기업정보 데이터 레이크 조사 에이전트

  --task <문장>        자유 형식 질문
  --task-file <경로>   질문을 파일에서 읽는다
  --preset <이름>      {presets}
  --company <이름|id>  프리셋 대상 기업. 상호 또는 company_id
                       (watchlist-monitor 제외 필수)
  --since <findings>   직전 실행 결과 (watchlist-monitor용)
  --data <경로>        기본 ./data
  --out <경로>         기본 ./artifacts
  --workspace <경로>   기본 ./workspace
  --model <id>         기본 {DEFAULT_MODEL}

인증은 .env의 ANTHROPIC_API_KEY (anthropic/* 모델),
또는 AWS_BEARER_TOKEN_BEDROCK + AWS_REGION (bedrock/* 모델).",
        presets = Preset::ALL.join(" | "),
    );
}

/// `1787199691-hanul-supply-chain-risk` 꼴. 실행마다 유일해야 하므로 앞에 epoch 초를
/// 붙인다. 날짜가 아니라 초인 것은 날짜 포맷팅 크레이트를 끌어오지 않기 위해서다.
fn run_slug(args: &Args) -> String {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let label = args
        .preset
        .map(|p| p.slug().to_string())
        .unwrap_or_else(|| "adhoc".to_string());
    let company = args
        .company
        .as_deref()
        .map(slugify)
        .filter(|s| !s.is_empty());
    match company {
        Some(c) => format!("{stamp}-{c}-{label}"),
        None => format!("{stamp}-{label}"),
    }
}

/// LM 호출의 토큰 사용량 누계.
///
/// Anthropic 계열은 매 호출의 `input_tokens`가 그 시점까지의 **대화 전체**다.
/// 그래서 합계는 고유 토큰 수가 아니라 **과금 기준 총량**이고, 요금은 이 값에
/// 요율을 곱해서 나온다. 대화가 얼마나 커졌는지는 `peak_input`이 답한다.
#[derive(Default)]
struct Usage {
    calls: usize,
    input: u64,
    output: u64,
    cache_read: u64,
    cache_write: u64,
    peak_input: u64,
}

impl Usage {
    fn add(&mut self, u: Option<&TokenUsage>) {
        let Some(u) = u else { return };
        self.calls += 1;
        self.input += u.input_tokens;
        self.output += u.output_tokens;
        self.cache_read += u.cache_read_input_tokens.unwrap_or(0);
        self.cache_write += u.cache_creation_input_tokens.unwrap_or(0);
        self.peak_input = self.peak_input.max(u.input_tokens);
    }
}

impl std::fmt::Display for Usage {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if self.calls == 0 {
            return f.write_str("토큰 사용량: 알 수 없음 (프로바이더가 usage를 보내지 않았다)");
        }
        write!(
            f,
            "토큰 (LM 호출 {}회): 입력 {} / 출력 {}",
            self.calls,
            thousands(self.input),
            thousands(self.output)
        )?;
        if self.cache_read > 0 || self.cache_write > 0 {
            write!(
                f,
                " / 캐시 읽기 {} / 캐시 쓰기 {}",
                thousands(self.cache_read),
                thousands(self.cache_write)
            )?;
        }
        write!(f, "\n  최대 컨텍스트 {} (마지막 호출 기준 대화 크기)", thousands(self.peak_input))
    }
}

/// `1234567` → `1,234,567`.
fn thousands(n: u64) -> String {
    let s = n.to_string();
    let mut out = String::with_capacity(s.len() + s.len() / 3);
    for (i, c) in s.chars().enumerate() {
        if i > 0 && (s.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(c);
    }
    out
}

/// 비영숫자를 `-`로 바꾸고 연속된 것은 하나로 접는다.
fn slugify(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        if c.is_alphanumeric() {
            out.extend(c.to_lowercase());
        } else if !out.ends_with('-') {
            out.push('-');
        }
    }
    out.trim_matches('-').to_string()
}

#[tokio::main]
async fn main() -> Result<()> {
    // 크레이트는 .env를 자동으로 읽지 않는다 (dotenvy 호출이 #[cfg(test)] 안에 있다).
    dotenvy::dotenv().ok();
    let args = parse_args()?;

    if !args.data.is_dir() {
        bail!("데이터 디렉터리가 없다: {}", args.data.display());
    }
    ensure_provider(&args.model)?;

    // 세션 트리. 게스트는 이 디렉터리만 보므로 data/·artifacts/·workspace/가
    // 전부 그 아래 있어야 한다.
    let tree = std::env::current_dir()?.canonicalize()?;
    for (label, path) in [
        ("--data", &args.data),
        ("--out", &args.out),
        ("--workspace", &args.workspace),
    ] {
        let abs = tree.join(path);
        if !abs.starts_with(&tree) {
            bail!(
                "{label} {} 이(가) 세션 트리 {} 밖에 있다. \
                 게스트에 공유되지 않아 접근할 수 없다.",
                path.display(),
                tree.display()
            );
        }
    }

    let slug = run_slug(&args);
    let artifacts_dir = args.out.join(&slug);
    let workspace_dir = args.workspace.join(&slug);
    std::fs::create_dir_all(&artifacts_dir)?;
    std::fs::create_dir_all(&workspace_dir)?;

    let boundary = WriteBoundary::new([artifacts_dir.clone(), workspace_dir.clone()]);
    boundary.check(&artifacts_dir.join("report.md"))?;

    // 실행 전 지문. data/가 정말 안 건드려졌는지는 말이 아니라 이걸로 판정한다.
    let before = DataFingerprint::scan(&args.data)?;
    println!("데이터 {}개 파일, 지문 확보", before.len());

    let task = build_task(&args)?;
    let paths = Paths {
        data: &args.data.to_string_lossy(),
        workspace: &args.workspace.to_string_lossy(),
        artifacts: &args.out.to_string_lossy(),
    };
    let instruction = prompt::instruction(&paths, args.preset, &slug);

    let mut agent = AgentBuilder::new(&args.model)
        .instruction(instruction)
        .system_tools()
        .python_repl_tool()
        .console(console().await?)
        .build()
        .context("에이전트 조립")?;

    println!("모델 {}", args.model);
    println!(
        "콘솔 {} (호스트에서 직접 실행 — 위반은 사후 검출뿐이다)",
        console_program()
    );
    println!("트리 {}", tree.display());
    println!("작업 {}\n", slug);

    let mut turns = 0usize;
    let mut tool_calls = 0usize;
    // 루프는 finish_reason이 ToolCall이 아닌 순간 끝난다. 산출물이 없을 때
    // 왜 멈췄는지는 이 값이 유일한 단서라 붙들고 있는다.
    let mut last_finish = None;
    let mut usage = Usage::default();
    let mut stream = agent.run(Message::new(Role::User).with_contents([Part::text(task)]));
    while let Some(output) = stream.next().await {
        let output = output?;
        turns += 1;
        if output.message.role == Role::Assistant {
            last_finish = Some(format!("{:?}", output.finish_reason));
        }
        for part in &output.message.contents {
            match part {
                Part::Text { text } if output.message.role == Role::Assistant => {
                    println!("{text}");
                }
                _ => {}
            }
        }
        tool_calls += output.message.tool_calls.as_ref().map_or(0, |c| c.len());
        usage.add(output.usage.as_ref());
    }
    drop(stream);

    // 실행 후 판정.
    let after = DataFingerprint::scan(&args.data)?;
    let violated = before.diff(&after);
    let written = list_files(&artifacts_dir);

    println!("\n--- 실행 요약 ---");
    println!("턴 {turns} / 툴 호출 {tool_calls}");
    println!("{usage}");
    println!(
        "종료 사유 {}",
        last_finish.as_deref().unwrap_or("(assistant 응답 없음)")
    );
    println!("산출물 {}개:", written.len());
    for p in &written {
        println!("  {}", p.display());
    }
    match &violated {
        // 어느 콘솔이든 이건 검출이지 강제가 아니다. uvm이 막는 것은 트리 *밖*이고,
        // 트리 자체는 virtio-fs로 쓰기 가능하게 공유된다.
        None => println!(
            "data/ 무결성: 통과 ({}개 파일 그대로 — 사후 검출 기준)",
            after.len()
        ),
        Some(d) => println!("data/ 무결성: **위반**\n{d}"),
    }
    let escaped: Vec<_> = written.iter().filter(|p| !boundary.permits(p)).collect();
    if !escaped.is_empty() {
        println!("쓰기 경계: **위반** {escaped:?}");
    }

    if violated.is_some() || !escaped.is_empty() {
        bail!("경계 위반이 검출되었다");
    }
    // 파일이 하나라도 생겼는지가 아니라 리포트가 나왔는지를 본다. 쿼리 파일만 남기고
    // 중간에 끊긴 실행을 성공으로 세면 검증이 무의미하다.
    if !written.iter().any(|p| p.file_name().is_some_and(|n| n == "report.md")) {
        bail!(
            "report.md가 없다 (산출물 {}개, 종료 사유 {}). \
             Length면 max_tokens에 걸린 것이고, Stop이면 쓰겠다고 말만 하고 턴을 끝낸 것이다.",
            written.len(),
            last_finish.as_deref().unwrap_or("?")
        );
    }

    // 실행 디렉터리는 슬러그로 흩어져 있어 리포트만 훑어보기 어렵다. 최종 산출물
    // 하나를 한 곳에 모아 둔다. 원본은 그대로 두고 복사만 한다.
    let filed = file_report(&artifacts_dir, &slug)?;
    println!("리포트 사본 {}", filed.display());

    Ok(())
}

/// `artifacts/<slug>/report.md`를 `reports/<slug>.md`로 복사한다.
fn file_report(artifacts_dir: &Path, slug: &str) -> Result<PathBuf> {
    let src = artifacts_dir.join("report.md");
    let dir = PathBuf::from("reports");
    std::fs::create_dir_all(&dir).with_context(|| format!("만들기 {}", dir.display()))?;
    let dst = dir.join(format!("{slug}.md"));
    std::fs::copy(&src, &dst)
        .with_context(|| format!("복사 {} -> {}", src.display(), dst.display()))?;
    Ok(dst)
}

fn build_task(args: &Args) -> Result<String> {
    let mut task = match (&args.task, args.preset) {
        (Some(t), _) => t.clone(),
        (None, Some(p)) => p.task(args.company.as_deref().unwrap_or("")),
        (None, None) => unreachable!("parse_args가 걸러낸다"),
    };
    if let Some(since) = &args.since {
        let prev = std::fs::read_to_string(since)
            .with_context(|| format!("직전 결과 읽기 {}", since.display()))?;
        task.push_str("\n\n# 직전 실행 결과 (이것과 비교해 변화만 보고한다)\n\n```json\n");
        task.push_str(&prev);
        task.push_str("\n```\n");
    }
    Ok(task)
}

fn list_files(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(dir) else {
        return out;
    };
    for e in entries.flatten() {
        let p = e.path();
        if p.is_dir() {
            out.extend(list_files(&p));
        } else {
            out.push(p);
        }
    }
    out.sort();
    out
}

/// 콘솔 서버 바이너리. `$AILOY_CORTEX_CONSOLE` > `build.rs`가 설치한 것 > `PATH` 순.
fn console_program() -> String {
    if let Ok(path) = std::env::var("AILOY_CORTEX_CONSOLE") {
        return path;
    }
    if Path::new(CONSOLE_INSTALLED).is_file() {
        return CONSOLE_INSTALLED.to_string();
    }
    CONSOLE_PROGRAM.to_string()
}

/// 빌트인 툴은 콘솔 없이는 실행되지 않는다.
///
/// 트리를 따로 선언하지 않는다. 이 서버는 마운트가 없으면 자신의 `current_dir()`을
/// 세션 디렉터리로 삼고, 이 프로세스의 cwd가 곧 트리이므로 결과가 같다.
async fn console() -> Result<Console> {
    let program = console_program();
    let mut console = Console::builder()
        .stdio_client(&[&program])
        .build()
        .await
        .with_context(|| {
            format!(
                "콘솔 서버 '{program}' 실행 실패. `cargo build`가 \
                 cortex-local-console를 설치하지 못했을 수 있다 — \
                 직접 빌드한 바이너리가 있으면 $AILOY_CORTEX_CONSOLE로 지정해라."
            )
        })?;
    console.start().await.context("콘솔 시작")?;
    Ok(console)
}

/// 모델이 등록된 프로바이더에 잡히는지 미리 확인한다.
/// 조립까지 갔다가 호출 시점에 실패하면 원인을 찾기 어렵다.
fn ensure_provider(model: &str) -> Result<()> {
    let providers = get_lm_providers_mut();
    let default = providers
        .get("default")
        .expect("default 프로바이더는 항상 있다");
    if default.get(model).is_some() {
        return Ok(());
    }
    drop(providers);

    // 등록이 안 됐다면 환경변수를 짚어 무엇이 빠졌는지 알려준다.
    for (prefix, var, hint) in [
        (
            "anthropic/",
            "ANTHROPIC_API_KEY",
            "console.anthropic.com > API keys 에서 발급한다.",
        ),
        (
            "bedrock/",
            "AWS_BEARER_TOKEN_BEDROCK",
            "Bedrock 콘솔 > API keys 에서 발급한다.",
        ),
    ] {
        if !model.starts_with(prefix) {
            continue;
        }
        if std::env::var(var).unwrap_or_default().trim().is_empty() {
            bail!(
                "{var}이 비어 있다. .env를 채워라 (.env.example 참조).\n\
                 {hint}"
            );
        }
    }
    bail!(
        "모델 '{model}'에 맞는 프로바이더가 없다. \
         .env에 해당 API 키가 있는지, 모델 접두사가 맞는지 확인해라."
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn usage_sums_billed_input_and_tracks_the_peak() {
        let mut u = Usage::default();
        u.add(Some(&TokenUsage {
            input_tokens: 1_000,
            output_tokens: 50,
            cache_creation_input_tokens: None,
            cache_read_input_tokens: Some(900),
        }));
        u.add(Some(&TokenUsage {
            input_tokens: 12_345,
            output_tokens: 60,
            cache_creation_input_tokens: Some(11),
            cache_read_input_tokens: None,
        }));
        u.add(None); // 툴 결과는 usage가 없다 — 호출 수에 세지 않는다
        assert_eq!(u.calls, 2);
        assert_eq!(u.input, 13_345);
        assert_eq!(u.output, 110);
        assert_eq!(u.cache_read, 900);
        assert_eq!(u.cache_write, 11);
        // 합계가 아니라 가장 큰 한 번이 대화 크기다
        assert_eq!(u.peak_input, 12_345);
        assert!(u.to_string().contains("13,345"));
    }

    #[test]
    fn thousands_groups_from_the_right() {
        for (n, want) in [(0, "0"), (7, "7"), (100, "100"), (1_000, "1,000"), (1_234_567, "1,234,567")] {
            assert_eq!(thousands(n), want, "{n}");
        }
    }

    #[test]
    fn slugify_handles_hangul_and_punctuation() {
        assert_eq!(slugify("한울소재(주)"), "한울소재-주");
        assert_eq!(slugify("Acme Materials Co., Ltd."), "acme-materials-co-ltd");
        assert_eq!(slugify("---"), "");
    }

    #[test]
    fn missing_bedrock_key_names_the_variable() {
        // 프로바이더가 없을 때의 오류가 무엇을 고쳐야 하는지 말해줘야 한다
        let err = ensure_provider("bedrock/nonexistent-model-xyz").unwrap_err();
        let msg = err.to_string();
        assert!(
            msg.contains("AWS_BEARER_TOKEN_BEDROCK") || msg.contains("프로바이더가 없다"),
            "{msg}"
        );
    }
}
