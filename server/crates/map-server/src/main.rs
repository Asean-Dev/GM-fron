use map_server::Config;
use tokio::net::TcpListener;

const MAP_SIZE: u32 = 100;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let addr = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "0.0.0.0:7000".into());
    let listener = TcpListener::bind(&addr).await?;
    tracing::info!("map server listening on {addr} ({MAP_SIZE}x{MAP_SIZE} map)");

    map_server::run(
        listener,
        Config {
            map_width: MAP_SIZE,
            map_height: MAP_SIZE,
        },
    )
    .await;
    Ok(())
}
