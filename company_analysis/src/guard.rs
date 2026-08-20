//! 쓰기 경계 강제와 검출.
//!
//! 인스트럭션은 `data/`가 읽기 전용이라고 말하지만, 말한 것과 지켜진 것은 다르다.
//! 여기서는 지켜졌는지를 실행 전후 해시로 확인하고, 산출물이 허용된 경로 밖으로
//! 나가지 않았는지 본다. 모델이 개입하지 않으므로 API 키 없이 전부 검증된다.

use std::{
    collections::BTreeMap,
    path::{Component, Path, PathBuf},
};

use anyhow::{Context, Result, bail};

/// `data/` 아래 모든 파일의 상대경로 → 내용 해시.
///
/// 파일 목록까지 담으므로 수정뿐 아니라 추가·삭제도 잡힌다.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DataFingerprint {
    files: BTreeMap<PathBuf, u64>,
}

impl DataFingerprint {
    pub fn scan(root: &Path) -> Result<Self> {
        let mut files = BTreeMap::new();
        collect(root, root, &mut files)
            .with_context(|| format!("fingerprinting {}", root.display()))?;
        if files.is_empty() {
            bail!("데이터 디렉터리가 비어 있다: {}", root.display());
        }
        Ok(Self { files })
    }

    pub fn len(&self) -> usize {
        self.files.len()
    }

    /// 변경을 사람이 읽는 형태로. 같으면 `None`.
    pub fn diff(&self, after: &Self) -> Option<String> {
        if self == after {
            return None;
        }
        let mut lines = Vec::new();
        for (path, hash) in &self.files {
            match after.files.get(path) {
                None => lines.push(format!("  삭제됨  {}", path.display())),
                Some(h) if h != hash => lines.push(format!("  수정됨  {}", path.display())),
                _ => {}
            }
        }
        for path in after.files.keys() {
            if !self.files.contains_key(path) {
                lines.push(format!("  추가됨  {}", path.display()));
            }
        }
        Some(lines.join("\n"))
    }
}

fn collect(root: &Path, dir: &Path, out: &mut BTreeMap<PathBuf, u64>) -> Result<()> {
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            collect(root, &path, out)?;
        } else {
            let rel = path.strip_prefix(root).unwrap_or(&path).to_path_buf();
            out.insert(rel, fnv1a(&std::fs::read(&path)?));
        }
    }
    Ok(())
}

/// 내용 해시. 충돌 저항성이 아니라 우발적 변경 검출이 목적이라 FNV-1a로 충분하다.
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in bytes {
        h ^= *b as u64;
        h = h.wrapping_mul(0x1000_0000_01b3);
    }
    h
}

/// 에이전트가 쓸 수 있는 경로.
#[derive(Debug, Clone)]
pub struct WriteBoundary {
    allowed: Vec<PathBuf>,
}

impl WriteBoundary {
    pub fn new(allowed: impl IntoIterator<Item = PathBuf>) -> Self {
        Self {
            allowed: allowed.into_iter().collect(),
        }
    }

    /// `path`가 허용된 루트 안에 있는지.
    ///
    /// 존재하지 않는 경로도 판정해야 하므로(쓰기 *전에* 묻는다) `canonicalize`를
    /// 쓸 수 없다. `..`를 직접 접어서 비교한다.
    pub fn permits(&self, path: &Path) -> bool {
        let Some(target) = normalize(path) else {
            return false; // 루트 위로 벗어나는 경로
        };
        self.allowed
            .iter()
            .filter_map(|a| normalize(a))
            .any(|root| target.starts_with(&root))
    }

    pub fn check(&self, path: &Path) -> Result<()> {
        if self.permits(path) {
            Ok(())
        } else {
            bail!(
                "쓰기 경계 위반: {} (허용: {})",
                path.display(),
                self.allowed
                    .iter()
                    .map(|p| p.display().to_string())
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
    }
}

/// 파일시스템을 건드리지 않고 `.`/`..`를 접는다. 루트 위로 올라가면 `None`.
fn normalize(path: &Path) -> Option<PathBuf> {
    let mut out = PathBuf::new();
    for c in path.components() {
        match c {
            Component::CurDir => {}
            Component::ParentDir => {
                if !out.pop() {
                    return None;
                }
            }
            other => out.push(other.as_os_str()),
        }
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp() -> PathBuf {
        let d = std::env::temp_dir().join(format!("ca-guard-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(d.join("sub")).unwrap();
        std::fs::write(d.join("a.csv"), b"1,2\n").unwrap();
        std::fs::write(d.join("sub/b.json"), b"{}").unwrap();
        d
    }

    #[test]
    fn fingerprint_detects_every_kind_of_change() {
        let d = tmp();
        let before = DataFingerprint::scan(&d).unwrap();
        assert_eq!(before.len(), 2);
        assert!(before.diff(&DataFingerprint::scan(&d).unwrap()).is_none());

        std::fs::write(d.join("a.csv"), b"1,3\n").unwrap();
        assert!(before.diff(&DataFingerprint::scan(&d).unwrap()).unwrap().contains("수정됨"));

        std::fs::write(d.join("c.csv"), b"x").unwrap();
        assert!(before.diff(&DataFingerprint::scan(&d).unwrap()).unwrap().contains("추가됨"));

        std::fs::remove_file(d.join("sub/b.json")).unwrap();
        assert!(before.diff(&DataFingerprint::scan(&d).unwrap()).unwrap().contains("삭제됨"));

        std::fs::remove_dir_all(&d).unwrap();
    }

    #[test]
    fn boundary_rejects_traversal_and_siblings() {
        let b = WriteBoundary::new([PathBuf::from("artifacts/run-1")]);
        assert!(b.permits(Path::new("artifacts/run-1/report.md")));
        assert!(b.permits(Path::new("artifacts/run-1/queries/01.sql")));
        assert!(b.permits(Path::new("./artifacts/run-1/x")));

        assert!(!b.permits(Path::new("data/CATALOG.md")));
        assert!(!b.permits(Path::new("artifacts/run-2/report.md")));
        // 접었을 때 data/로 빠지는 경로
        assert!(!b.permits(Path::new("artifacts/run-1/../../data/x.csv")));
        // 루트 위로 나가는 경로
        assert!(!b.permits(Path::new("../etc/passwd")));
        // 접두사만 같은 형제 디렉터리에 속으면 안 된다
        assert!(!b.permits(Path::new("artifacts/run-10/report.md")));
    }

    #[test]
    fn empty_data_dir_is_an_error() {
        let d = std::env::temp_dir().join(format!("ca-empty-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        assert!(DataFingerprint::scan(&d).is_err());
        std::fs::remove_dir_all(&d).unwrap();
    }
}
