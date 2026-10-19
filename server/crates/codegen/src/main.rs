//! Regenerates the Unity client's C# protocol code from `proto/`:
//!
//!     cargo run -p codegen

use std::path::Path;
use std::process::Command;

use anyhow::{Context, ensure};

fn main() -> anyhow::Result<()> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()?;
    let proto_dir = root.join("proto");
    let out_dir = root.join("client/Assets/Scripts/Generated");
    std::fs::create_dir_all(&out_dir)?;

    let status = Command::new(protoc_bin_vendored::protoc_bin_path()?)
        .arg(format!("--proto_path={}", proto_dir.display()))
        .arg(format!("--csharp_out={}", out_dir.display()))
        .arg(proto_dir.join("game.proto"))
        .status()
        .context("running protoc")?;
    ensure!(status.success(), "protoc failed: {status}");

    println!("wrote {}", out_dir.join("Game.cs").display());
    Ok(())
}
