fn main() -> std::io::Result<()> {
    let proto_dir = "../../../proto";
    println!("cargo:rerun-if-changed={proto_dir}");

    prost_build::Config::new()
        .protoc_executable(protoc_bin_vendored::protoc_bin_path().expect("vendored protoc"))
        .compile_protos(&[format!("{proto_dir}/game.proto")], &[proto_dir])
}
