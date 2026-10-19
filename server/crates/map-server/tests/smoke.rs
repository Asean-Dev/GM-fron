use std::net::SocketAddr;
use std::time::Duration;

use futures::{SinkExt, StreamExt};
use map_server::{Config, run};
use protocol::{ClientMsg, Message, ServerMsg, client_msg, encode, pb, server_msg::Msg};
use tokio::net::{TcpListener, TcpStream};
use tokio_util::codec::{Framed, LengthDelimitedCodec};

struct Client(Framed<TcpStream, LengthDelimitedCodec>);

impl Client {
    async fn join(addr: SocketAddr, name: &str) -> (Self, u32) {
        let stream = TcpStream::connect(addr).await.unwrap();
        let mut c = Client(Framed::new(stream, protocol::codec()));
        c.send(client_msg::Msg::Hello(pb::Hello { name: name.into() }))
            .await;
        let id = c
            .recv_until(|m| match m {
                Msg::Welcome(w) => Some(w.entity_id),
                _ => None,
            })
            .await;
        (c, id)
    }

    async fn send(&mut self, msg: client_msg::Msg) {
        self.0
            .send(encode(&ClientMsg { msg: Some(msg) }))
            .await
            .unwrap();
    }

    async fn recv_until<T>(&mut self, mut want: impl FnMut(Msg) -> Option<T>) -> T {
        loop {
            let frame = tokio::time::timeout(Duration::from_secs(3), self.0.next())
                .await
                .expect("timed out waiting for message")
                .expect("server closed connection")
                .unwrap();
            if let Some(t) = want(ServerMsg::decode(frame).unwrap().msg.unwrap()) {
                return t;
            }
        }
    }
}

#[tokio::test]
async fn players_see_each_other_join_move_and_leave() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(run(
        listener,
        Config {
            map_width: 20,
            map_height: 20,
        },
    ));

    let (mut alice, alice_id) = Client::join(addr, "alice").await;
    let (mut bob, bob_id) = Client::join(addr, "bob").await;

    // Bob's join snapshot includes Alice; Alice is told Bob arrived.
    let name = bob
        .recv_until(|m| match m {
            Msg::Spawn(s) if s.entity_id == alice_id => Some(s.name),
            _ => None,
        })
        .await;
    assert_eq!(name, "alice");
    alice
        .recv_until(|m| matches!(m, Msg::Spawn(s) if s.entity_id == bob_id).then_some(()))
        .await;

    // Alice clicks a cell; Bob watches her walk all the way there.
    alice
        .send(client_msg::Msg::MoveTo(pb::MoveTo { x: 2, y: 3 }))
        .await;
    bob.recv_until(|m| {
        matches!(m, Msg::Move(mv) if mv.entity_id == alice_id && (mv.x, mv.y) == (2, 3))
            .then_some(())
    })
    .await;

    drop(alice);
    bob.recv_until(|m| matches!(m, Msg::Despawn(d) if d.entity_id == alice_id).then_some(()))
        .await;
}

#[tokio::test]
async fn connection_must_start_with_hello() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(run(
        listener,
        Config {
            map_width: 20,
            map_height: 20,
        },
    ));

    let mut c = Client(Framed::new(
        TcpStream::connect(addr).await.unwrap(),
        protocol::codec(),
    ));
    c.send(client_msg::Msg::MoveTo(pb::MoveTo { x: 1, y: 1 }))
        .await;

    let next = tokio::time::timeout(Duration::from_secs(3), c.0.next())
        .await
        .unwrap();
    assert!(next.is_none(), "server should close the connection");
}
