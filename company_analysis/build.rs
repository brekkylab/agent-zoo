//! 콘솔 서버 바이너리를 여기서 확보한다. cortex를 손으로 clone하지 않아도
//! `cargo run`만으로 에이전트가 돌게 하려는 것이고, 리비전은 `Cargo.toml`의
//! `[patch]`가 고정한 cortex와 같아야 한다 — 콘솔 프로토콜이 링크된
//! `cortex` 라이브러리와 맞물려야 하기 때문이다.

use std::{env, path::PathBuf, process::Command};

const CORTEX_REPO: &str = "https://github.com/brekkylab/cortex";
const CORTEX_REV: &str = "5da0e4d029d5bd3e258d224c3ffa5aaa3088f2f9";
const CONSOLE_CRATE: &str = "cortex-local-console";

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=AILOY_CORTEX_CONSOLE");

    // 직접 지정한 경로가 있으면 빌드하지 않는다.
    if let Ok(path) = env::var("AILOY_CORTEX_CONSOLE") {
        println!("cargo:rustc-env=CORTEX_CONSOLE={path}");
        return;
    }

    let root = PathBuf::from(env::var("OUT_DIR").unwrap()).join("cortex-console");
    let bin = root.join("bin").join(CONSOLE_CRATE);
    println!("cargo:rustc-env=CORTEX_CONSOLE={}", bin.display());
    if bin.exists() {
        return;
    }

    let cargo = env::var("CARGO").unwrap_or_else(|_| "cargo".to_string());
    let status = Command::new(cargo)
        .args(["install", "--git", CORTEX_REPO, "--rev", CORTEX_REV, "--root"])
        .arg(&root)
        .arg(CONSOLE_CRATE)
        .status();

    // 여기서 실패해도 빌드는 세운다. PATH나 `$AILOY_CORTEX_CONSOLE`에 콘솔이
    // 이미 있을 수 있고, 없으면 실행 시점에 안내가 나간다.
    match status {
        Ok(s) if s.success() => {}
        Ok(s) => println!("cargo:warning={CONSOLE_CRATE} 설치 실패 ({s}). 실행 전 $AILOY_CORTEX_CONSOLE를 지정해라."),
        Err(e) => println!("cargo:warning=cargo install 실행 실패 ({e}). 실행 전 $AILOY_CORTEX_CONSOLE를 지정해라."),
    }
}
