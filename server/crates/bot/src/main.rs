//! Load-test bots: fake players that join the map server and click-to-move at random.
//!
//!     cargo run --release -p bot -- --count 200

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use anyhow::bail;
use clap::Parser;
use futures::{SinkExt, StreamExt};
use protocol::{ClientMsg, Message, ServerMsg, client_msg, encode, pb, server_msg};
use tokio::net::TcpStream;
use tokio_util::codec::Framed;

#[derive(Parser)]
struct Args {
    #[arg(long, default_value = "127.0.0.1:7000")]
    addr: String,
    #[arg(long, default_value_t = 50)]
    count: u32,
}

#[derive(Default)]
struct Stats {
    alive: AtomicU64,
    received: AtomicU64,
}

#[tokio::main]
async fn main() {
    let args = Args::parse();
    let stats = Arc::new(Stats::default());

    for n in 0..args.count {
        let (addr, stats) = (args.addr.clone(), stats.clone());
        tokio::spawn(async move {
            if let Err(e) = bot(&addr, n, &stats).await {
                eprintln!("bot-{n}: {e:#}");
            }
        });
        // Stagger connects so the server isn't hit by all joins at once.
        tokio::time::sleep(Duration::from_millis(5)).await;
    }

    let mut report = tokio::time::interval(Duration::from_secs(5));
    report.tick().await;
    loop {
        report.tick().await;
        let received = stats.received.swap(0, Ordering::Relaxed);
        println!(
            "bots alive: {:>5}   msgs received/s: {:>8}",
            stats.alive.load(Ordering::Relaxed),
            received / 5
        );
    }
}

async fn bot(addr: &str, n: u32, stats: &Arc<Stats>) -> anyhow::Result<()> {
    let stream = TcpStream::connect(addr).await?;
    stream.set_nodelay(true)?;
    let (mut sink, mut frames) = Framed::new(stream, protocol::codec()).split();

    let hello = client_msg::Msg::Hello(pb::Hello {
        name: format!("bot-{n}"),
    });
    sink.send(encode(&ClientMsg { msg: Some(hello) })).await?;

    let (width, height) = loop {
        let Some(frame) = frames.next().await else {
            bail!("closed before Welcome")
        };
        if let Some(server_msg::Msg::Welcome(w)) = ServerMsg::decode(frame?)?.msg {
            break (w.map_width as i32, w.map_height as i32);
        }
    };

    stats.alive.fetch_add(1, Ordering::Relaxed);
    let reader_stats = stats.clone();
    let reader = tokio::spawn(async move {
        while let Some(Ok(_)) = frames.next().await {
            reader_stats.received.fetch_add(1, Ordering::Relaxed);
        }
    });

    let result = async {
        loop {
            tokio::time::sleep(Duration::from_millis(rand::random_range(1000..3000))).await;
            if reader.is_finished() {
                bail!("server closed the connection");
            }
            let target = pb::MoveTo {
                x: rand::random_range(0..width),
                y: rand::random_range(0..height),
            };
            let msg = ClientMsg {
                msg: Some(client_msg::Msg::MoveTo(target)),
            };
            sink.send(encode(&msg)).await?;
        }
    }
    .await;

    stats.alive.fetch_sub(1, Ordering::Relaxed);
    reader.abort();
    result
}
