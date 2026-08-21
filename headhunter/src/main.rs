//! headhunter 예제 — JD 를 읽고 후보를 찾아 숏리스트와 콜드메일 초안을 쓴다.
//!
//! # 새 툴 코드가 없다
//!
//! cortex 의 delegation 이 delegated 이름을 PATH 심볼릭 링크로 실체화하므로, `sqlite` 를
//! 등록하면 ailoy 의 기존 `shell` 툴이 그것을 부른다 — `console.exec(["sh", "-c", cmd])`
//! 가 이미 그 경로다. 어댑터가 0줄인 것이 spec §1.2 의 결론이고,
//! `cortex-console-servers/local/tests/exec_sqlite.rs` 가 실제 서버 프로세스를 거쳐
//! 실증했다.
//!
//! 그래서 이 파일이 하는 일은 셋뿐이다 — CLI 를 읽고, 콘솔을 조립하고, 에이전트를 돌린다.

use ailoy::{lang_model::get_lm_providers_mut, message::Role};
use anyhow::{Context, Result, bail};
use clap::Parser;
use cortex::{
    console::{Console, stdio::StdioClient},
    exec::ExecutableSet,
    fs::Mount,
};
use cortex_exec_sqlite::Sqlite;
use futures::StreamExt;
// `std::process::Command` 가 아니다 — `StdioClient` 가 런타임에서 파이프를 읽고 쓰므로
// async 쪽을 받는다. 계획 A 의 통과 테스트가 같은 자리에 같은 주석을 달았다.
use tokio::process::Command;

mod prompt;

#[derive(Parser)]
#[command(about = "채용공고를 읽고 인재풀에서 상위 k명을 골라 콜드메일 초안을 쓴다")]
struct Args {
    /// JD 마크다운 경로.
    #[arg(long, default_value = "jd.md")]
    jd: std::path::PathBuf,

    /// 숏리스트에 낼 인원. 적격자가 이보다 적으면 적게 내고 이유를 쓴다.
    #[arg(long, default_value_t = 3)]
    k: usize,

    /// 산출물을 쓸 디렉터리. JD 이름으로 하위 디렉터리를 만든다.
    #[arg(long, default_value = "artifacts")]
    out: std::path::PathBuf,

    /// 모델 식별자.
    ///
    /// `<provider>/<model>` 형식이고 프로바이더는 환경변수로 등록된다. 기본값이
    /// Bedrock 인 이유는 이 예제가 그것으로 돌려졌기 때문이다 —
    /// `AWS_BEARER_TOKEN_BEDROCK` 과 `AWS_REGION` 을 읽는다.
    ///
    /// **Bedrock 쪽 모델 이름은 inference-profile id 여야 한다.**
    /// `global.anthropic.claude-sonnet-5` 처럼 접두어가 붙은 것이고, 맨 foundation-model
    /// id 는 on-demand throughput 에서 거부된다.
    ///
    /// 다른 프로바이더도 그대로 쓸 수 있다 — `--model anthropic/claude-sonnet-5` 이면
    /// `ANTHROPIC_API_KEY` 를 읽는다.
    #[arg(long, default_value = "bedrock/global.anthropic.claude-sonnet-5")]
    model: String,

    /// 콘솔 서버 바이너리. cortex 형제 체크아웃에서 빌드한 것.
    #[arg(
        long,
        env = "AILOY_CORTEX_CONSOLE",
        default_value = "cortex-local-console"
    )]
    console: std::path::PathBuf,

    /// 한 응답에 모델이 낼 수 있는 최대 토큰.
    ///
    /// **기본값(Anthropic 8192)으로는 이 예제가 실패한다.** 숏리스트를 `write` 툴로
    /// 쓰는데 파일 본문이 툴 호출 인자에 실려 응답 토큰에 그대로 잡히기 때문이다.
    /// 실측: 10KB 짜리 숏리스트를 쓰려다 `FinishReason::Length` 로 끝나고 산출물이
    /// 0개가 나왔다 — 47턴을 돌고 아무것도 안 남았다.
    #[arg(long, default_value_t = 32_000)]
    max_tokens: u64,
}

/// 모델에 맞는 프로바이더가 등록됐는지 **호출 전에** 확인한다.
///
/// 없으면 첫 LM 호출에서 죽는데, 그때 나오는 말이 "no provider found" 라 무엇이
/// 빠졌는지 알려주지 않는다. 어느 환경변수가 비었는지를 여기서 짚는다.
fn ensure_provider(model: &str) -> Result<()> {
    let providers = get_lm_providers_mut();
    let default = providers
        .get("default")
        .expect("default 프로바이더는 항상 있다");
    if default.get(model).is_some() {
        return Ok(());
    }
    drop(providers);

    let (var, hint) = match model.split('/').next() {
        Some("bedrock") => (
            "AWS_BEARER_TOKEN_BEDROCK",
            "Bedrock 콘솔 > API keys 에서 발급한다",
        ),
        Some("anthropic") => ("ANTHROPIC_API_KEY", "console.anthropic.com 에서 발급한다"),
        Some("openai") => ("OPENAI_API_KEY", ""),
        _ => ("", ""),
    };
    if !var.is_empty() && std::env::var(var).unwrap_or_default().trim().is_empty() {
        bail!("{var} 가 비어 있다. 저장소 루트 `.env` 를 채워라. {hint}");
    }
    bail!(
        "모델 '{model}' 에 맞는 프로바이더가 없다. `.env` 에 해당 API 키가 있는지, \
         모델 접두사(`bedrock/` · `anthropic/` …)가 맞는지 확인해라"
    )
}

/// 작업 트리 — 콘솔이 트리로 취급할 디렉터리.
///
/// `Mount` 는 커널 마운트를 뜻하지 않는다. 필수 메서드가 `mountpoint()` 하나이고,
/// `PathBuf` 는 이것을 구현하지 않으므로 다섯 줄을 직접 쓴다.
///
/// FUSE 는 필요 없다. cortex 의 `FuseTMount`/`FuseMount` 는 커널이 실제로 답해야 할 때를
/// 위한 것이고 `fuser` optional feature 뒤에 있다. 호스트 디렉터리 하나를 트리로 쓰는
/// 데는 쓰이지 않는다 — `local/tests/exec_sqlite.rs` 의 `Mounted` 가 같은 다섯 줄이고
/// 그 테스트가 실제 서버를 거쳐 통과한다.
struct Tree(std::path::PathBuf);

impl Mount for Tree {
    fn mountpoint(&self) -> &std::path::Path {
        &self.0
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // 저장소 루트의 `.env` 를 읽는다. 없으면 조용히 넘어가고 이미 설정된 환경변수를 쓴다.
    //
    // ailoy 본체에도 `dotenvy::dotenv()` 가 있지만 `#[cfg(test)]` 안이라 테스트에서만
    // 돈다. 바이너리는 직접 불러야 하고, 안 부르면 `.env` 에 키를 넣어 두고도
    // "no provider found" 를 본다.
    //
    // `dotenv()` 는 현재 디렉터리부터 위로 올라가며 찾으므로, `examples/headhunter` 에서
    // 돌리든 저장소 루트에서 돌리든 같은 파일을 집는다.
    dotenvy::dotenv().ok();

    let args = Args::parse();
    ensure_provider(&args.model)?;
    let jd = std::fs::read_to_string(&args.jd)
        .with_context(|| format!("JD 읽기 {}", args.jd.display()))?;

    // 에이전트가 `sqlite data/headhunter.db '<SQL>'` 을 부를 때 그 경로는 **워크스페이스
    // 기준**이지 호스트 경로가 아니다. 그래서 현재 디렉터리를 통째로 마운트한다 —
    // `data/` 도 `artifacts/` 도 그 아래다.
    let root = std::env::current_dir()?;

    let mut server = Command::new(&args.console);
    // 서버가 못 뜨면 이유가 이쪽 stderr 로 나오게 둔다. 조용히 실패하면 원인이
    // "콘솔이 안 붙는다" 한 줄로만 보인다.
    server.stderr(std::process::Stdio::inherit());

    let console = Console::builder()
        .client(StdioClient::new(server)?)
        .mount(Tree(root.clone()))
        .executables(ExecutableSet::new().register("sqlite", Sqlite::summary(), Sqlite::new()))
        .build()
        .await?;

    // `Console::builder().build()` 만 await 한다 — `AgentBuilder::build()` 는 async 가
    // 아니다.
    // **`system_tools()` 가 없으면 에이전트가 아무것도 못 한다.** 콘솔을 붙이는 것과
    // 툴을 등록하는 것은 별개다 — 콘솔은 툴이 명령을 실행할 장소이고, 툴이 없으면
    // 실행할 주체가 없다.
    //
    // 처음에 이것을 빠뜨렸고 **실패가 조용했다.** 지침은 "You have a `shell` tool" 이라고
    // 말하는데 실제로는 없으니, 모델이 부를 것이 없어 명령을 산문으로 흉내 냈다:
    //
    //     `sqlite data/headhunter.db 'PRAGMA table_info(candidates)'`
    //
    // 그것은 툴 호출이 아니라 그냥 텍스트다. 모델이 턴을 끝내고 스트림도 끝나서,
    // 에러 없이 **exit 0 으로 한 턴 만에** 종료했다.
    //
    // `system_tools()` 는 `shell`·`read`·`write`·`edit`·`glob`·`grep` 을 준다.
    // `shell` 이 `sqlite` 를 부르고(delegation 이 PATH 에 올려 둔다), `write` 가
    // 산출물을 쓴다. 개별로 붙이지 않는 이유는 이 목록이 모델 계열에 따라 갈리기
    // 때문이다 — openai 계열은 `apply_patch` 를 받는다.
    let mut agent = ailoy::agent::AgentBuilder::new(&args.model)
        .console(console)
        .system_tools()
        .max_tokens(args.max_tokens)
        .instruction(prompt::system(args.k, &args.out))
        .build()?;

    let jd_slug = args
        .jd
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| "role".to_string());
    let out_dir = args.out.join(&jd_slug);

    println!("  모델   {}", args.model);
    println!("  콘솔   {}", args.console.display());
    println!("  트리   {}", root.display());
    println!("  산출   {}", out_dir.display());
    println!("  최대   {} 토큰/응답\n", args.max_tokens);

    // `run` 은 스트림을 돌려준다 — 단일 future 가 아니다. 소비해야 턴이 돈다.
    //
    // **종료 사유를 붙들고 있는다.** 산출물이 없을 때 왜 멈췄는지의 유일한 단서다.
    // `Stop` 이면 쓰겠다고 말만 하고 턴을 끝낸 것이고, `Length` 면 max_tokens 다.
    let mut turns = 0usize;
    let mut tool_calls = 0usize;
    let mut last_finish: Option<String> = None;
    let mut stream = agent.run(prompt::user(&jd, &args.jd));
    while let Some(output) = stream.next().await {
        let output = output?;
        turns += 1;
        if output.message.role == Role::Assistant {
            last_finish = Some(format!("{:?}", output.finish_reason));
        }
        tool_calls += output.message.tool_calls.as_ref().map_or(0, |c| c.len());
        print!("{}", render(&output));
        use std::io::Write;
        std::io::stdout().flush()?;
    }
    drop(stream);

    let written = list_files(&out_dir);
    println!("\n--- 실행 요약 ---");
    println!("턴 {turns} / 툴 호출 {tool_calls}");
    println!(
        "종료 사유 {}",
        last_finish.as_deref().unwrap_or("(assistant 응답 없음)")
    );
    println!("산출물 {}개:", written.len());
    for p in &written {
        println!("  {}", p.display());
    }

    // **파일이 생겼는지가 아니라 숏리스트가 나왔는지를 본다.** 메일 초안만 남기고
    // 중간에 끊긴 실행을 성공으로 세면 검증이 무의미하다. 그리고 툴 호출이 0 이면
    // 에이전트가 명령을 산문으로 흉내 낸 것이다 — 실제로 그렇게 실패한 적이 있다.
    if tool_calls == 0 {
        bail!(
            "툴 호출이 0회다 (턴 {turns}, 종료 사유 {}). 에이전트가 명령을 실행하지 않고 \
             텍스트로 적었을 가능성이 크다 — `system_tools()` 가 붙어 있는지 확인해라",
            last_finish.as_deref().unwrap_or("?")
        );
    }
    if !written
        .iter()
        .any(|p| p.file_name().is_some_and(|n| n == "00-shortlist.md"))
    {
        bail!(
            "00-shortlist.md 가 없다 (산출물 {}개, 종료 사유 {}). Length 면 max_tokens 에 \
             걸린 것이고, Stop 이면 쓰겠다고 말만 하고 턴을 끝낸 것이다",
            written.len(),
            last_finish.as_deref().unwrap_or("?")
        );
    }

    println!("\n채점: eval/run_eval.py --score {}", out_dir.display());
    Ok(())
}

/// 디렉터리 바로 아래 파일들. 재귀하지 않는다 — 산출물은 한 층이다.
fn list_files(dir: &std::path::Path) -> Vec<std::path::PathBuf> {
    let mut out: Vec<_> = std::fs::read_dir(dir)
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
        .filter(|p| p.is_file())
        .collect();
    out.sort();
    out
}

/// 툴 결과에서 화면에 흘릴 최대 줄 수.
///
/// 이 예제의 쿼리는 수백 행을 돌려준다(`MATCH 'rust'` 하나가 83행이다). 전부 흘리면
/// 에이전트의 판단이 결과 표에 묻히므로 앞부분만 보이고 나머지는 줄 수로 알린다.
const RESULT_LINES: usize = 8;

/// 한 줄로 눕힌 인자가 이보다 길면 자른다.
const ARGS_WIDTH: usize = 200;

/// 한 메시지에서 화면에 흘릴 것을 만든다.
///
/// # `contents` 만 보면 정작 보여줄 것이 안 보인다
///
/// 이 함수는 처음에 `message.contents` 의 `Part::Text` 만 통과시켰다. 근거는 "콘솔
/// 스트리밍이 이 예제의 목적이므로 보여줄 것은 에이전트의 말"이었는데, **그 근거가
/// 결론을 뒤집는다** — 콘솔을 붙인 이유가 도구 왕래이고, 그러면 화면에 흘러야 할 것은
/// 에이전트가 짜는 SQL 이다.
///
/// 그리고 도구 호출은 `contents` 에 없다. [`Message`] 가 `tool_calls` 라는 **별도
/// 필드**에 담는다(`src/message/message.rs`). `contents` 만 훑는 한 몇 줄을 고쳐도
/// SQL 은 절대 나타나지 않는다.
///
/// [`Message`]: ailoy::message::Message
fn render(output: &ailoy::message::MessageOutput) -> String {
    use ailoy::message::Part;

    let msg = &output.message;
    let mut out = String::new();

    if msg.role == Role::Tool {
        // 도구가 돌려준 것. 왼쪽 괘선으로 에이전트의 말과 구별한다.
        let body = text_of(&msg.contents);
        let mut lines = body.lines();
        for line in lines.by_ref().take(RESULT_LINES) {
            out.push_str("  │ ");
            out.push_str(line);
            out.push('\n');
        }
        let rest = lines.count();
        if rest > 0 {
            out.push_str(&format!("  └ … {rest}줄 더\n"));
        }
        return out;
    }

    out.push_str(&text_of(&msg.contents));

    // 에이전트가 부른 도구. `tool_calls` 는 `Option<Vec<Part>>` 이므로 `iter().flatten()`
    // 이 "없으면 0개" 를 그대로 처리한다.
    for call in msg.tool_calls.iter().flatten() {
        if let Part::Function { function, .. } = call {
            out.push_str(&format!(
                "\n▸ {} {}\n",
                function.name,
                args_line(&function.arguments)
            ));
        }
    }
    out
}

/// 파트 목록에서 텍스트만 이어붙인다.
fn text_of(parts: &[ailoy::message::Part]) -> String {
    parts
        .iter()
        .filter_map(|part| match part {
            ailoy::message::Part::Text { text } => Some(text.as_str()),
            _ => None,
        })
        .collect()
}

/// 툴 인자를 한 줄로 눕힌다.
///
/// 툴마다 인자 이름이 다르므로(`shell` 은 `command`, `read` 는 `file_path`) 키를 하나씩
/// 알아보는 대신 **스칼라 값을 순서대로 잇는다.** 여섯 개 시스템 툴 전부에 통한다.
///
/// 여러 줄 SQL 을 한 줄로 접는 것은 화면에서 한 호출이 한 줄이어야 읽히기 때문이다.
fn args_line(v: &ailoy::datatype::Value) -> String {
    use ailoy::datatype::Value;

    fn scalar(v: &Value) -> Option<String> {
        match v {
            Value::String(s) => Some(s.clone()),
            Value::Unsigned(n) => Some(n.to_string()),
            Value::Integer(n) => Some(n.to_string()),
            Value::Float(f) => Some(f.to_string()),
            Value::Bool(b) => Some(b.to_string()),
            _ => None,
        }
    }

    let joined = match v {
        Value::Object(map) => map.values().filter_map(scalar).collect::<Vec<_>>().join("  "),
        other => scalar(other).unwrap_or_default(),
    };
    let flat = joined.split_whitespace().collect::<Vec<_>>().join(" ");
    if flat.chars().count() > ARGS_WIDTH {
        let head: String = flat.chars().take(ARGS_WIDTH).collect();
        format!("{head}…")
    } else {
        flat
    }
}
