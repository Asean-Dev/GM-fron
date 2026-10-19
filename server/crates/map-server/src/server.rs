//! Networking: one task per connection, plus one task (the hub) that owns the World.
//! Connections talk to the hub over channels, so world state never needs a lock.

use std::collections::HashMap;
use std::time::Duration;

use anyhow::bail;
use futures::{SinkExt, Stream, StreamExt};
use protocol::{ClientMsg, Message, ServerMsg, client_msg, encode, pb, server_msg};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, oneshot};
use tokio::time::MissedTickBehavior;
use tokio_util::bytes::BytesMut;
use tokio_util::codec::Framed;

use crate::world::{Cell, Entity, EntityId, World};

/// Simulation rate. Ragnarok-style walking is one cell per tick.
pub const TICK: Duration = Duration::from_millis(100);
const HELLO_TIMEOUT: Duration = Duration::from_secs(5);
/// Messages queued per client before it counts as too slow and gets disconnected.
/// Must hold a full snapshot of the map on join.
const OUTBOX: usize = 4096;
const MAX_NAME_LEN: usize = 24;

pub struct Config {
    pub map_width: u32,
    pub map_height: u32,
}

enum Cmd {
    Join {
        name: String,
        outbox: mpsc::Sender<ServerMsg>,
        reply: oneshot::Sender<EntityId>,
    },
    MoveTo {
        id: EntityId,
        target: Cell,
    },
    Leave {
        id: EntityId,
    },
}

pub async fn run(listener: TcpListener, config: Config) {
    let (cmd_tx, cmd_rx) = mpsc::channel(1024);
    let hub = Hub {
        world: World::new(config.map_width, config.map_height),
        clients: HashMap::new(),
        dead: Vec::new(),
    };
    tokio::spawn(hub.run(cmd_rx));

    loop {
        let (stream, addr) = match listener.accept().await {
            Ok(conn) => conn,
            Err(e) => {
                // Usually out of file descriptors; back off instead of spinning.
                tracing::warn!("accept failed: {e}");
                tokio::time::sleep(Duration::from_millis(100)).await;
                continue;
            }
        };
        let cmd_tx = cmd_tx.clone();
        tokio::spawn(async move {
            match handle_conn(stream, cmd_tx).await {
                Ok(()) => tracing::debug!(%addr, "disconnected"),
                Err(e) => tracing::debug!(%addr, "disconnected: {e:#}"),
            }
        });
    }
}

async fn handle_conn(stream: TcpStream, cmds: mpsc::Sender<Cmd>) -> anyhow::Result<()> {
    stream.set_nodelay(true)?;
    let (mut sink, mut frames) = Framed::new(stream, protocol::codec()).split();

    let first = match tokio::time::timeout(HELLO_TIMEOUT, frames.next()).await {
        Ok(Some(frame)) => ClientMsg::decode(frame?)?,
        Ok(None) => return Ok(()),
        Err(_) => bail!("no Hello within {HELLO_TIMEOUT:?}"),
    };
    let Some(client_msg::Msg::Hello(hello)) = first.msg else {
        bail!("first message must be Hello");
    };

    let (outbox, mut out_rx) = mpsc::channel(OUTBOX);
    let (reply, id) = oneshot::channel();
    let name = clean_name(&hello.name);
    cmds.send(Cmd::Join {
        name,
        outbox,
        reply,
    })
    .await?;
    let id = id.await?;

    // Ends when the hub drops our outbox (we left, or were too slow) or the socket fails.
    let mut writer = tokio::spawn(async move {
        while let Some(msg) = out_rx.recv().await {
            sink.feed(encode(&msg)).await?;
            while let Ok(msg) = out_rx.try_recv() {
                sink.feed(encode(&msg)).await?;
            }
            sink.flush().await?;
        }
        anyhow::Ok(())
    });

    let result = tokio::select! {
        r = read_loop(&mut frames, &cmds, id) => r,
        r = &mut writer => r.unwrap_or_else(|e| Err(e.into())),
    };
    let _ = cmds.send(Cmd::Leave { id }).await;
    writer.abort();
    result
}

async fn read_loop(
    frames: &mut (impl Stream<Item = std::io::Result<BytesMut>> + Unpin),
    cmds: &mpsc::Sender<Cmd>,
    id: EntityId,
) -> anyhow::Result<()> {
    while let Some(frame) = frames.next().await {
        match ClientMsg::decode(frame?)?.msg {
            Some(client_msg::Msg::MoveTo(m)) => {
                let target = Cell { x: m.x, y: m.y };
                cmds.send(Cmd::MoveTo { id, target }).await?;
            }
            Some(client_msg::Msg::Hello(_)) => bail!("duplicate Hello"),
            None => {}
        }
    }
    Ok(())
}

fn clean_name(raw: &str) -> String {
    let name: String = raw
        .trim()
        .chars()
        .filter(|c| !c.is_control())
        .take(MAX_NAME_LEN)
        .collect();
    if name.is_empty() {
        "player".into()
    } else {
        name
    }
}

struct Hub {
    world: World,
    clients: HashMap<EntityId, mpsc::Sender<ServerMsg>>,
    /// Clients whose outbox was full or closed; removed by `reap`.
    dead: Vec<EntityId>,
}

impl Hub {
    async fn run(mut self, mut cmds: mpsc::Receiver<Cmd>) {
        let mut tick = tokio::time::interval(TICK);
        tick.set_missed_tick_behavior(MissedTickBehavior::Skip);
        loop {
            tokio::select! {
                cmd = cmds.recv() => match cmd {
                    Some(cmd) => self.handle(cmd),
                    None => return,
                },
                _ = tick.tick() => {
                    for (id, pos) in self.world.tick() {
                        self.broadcast(&server_msg::Msg::Move(pb::EntityMove {
                            entity_id: id,
                            x: pos.x,
                            y: pos.y,
                        }), None);
                    }
                }
            }
            self.reap();
        }
    }

    fn handle(&mut self, cmd: Cmd) {
        match cmd {
            Cmd::Join {
                name,
                outbox,
                reply,
            } => {
                let id = self.world.spawn(name);
                if reply.send(id).is_err() {
                    // The connection dropped while joining.
                    self.world.despawn(id);
                    return;
                }
                self.clients.insert(id, outbox);

                let (map_width, map_height) = self.world.size();
                self.send(
                    id,
                    server_msg::Msg::Welcome(pb::Welcome {
                        entity_id: id,
                        map_width,
                        map_height,
                    }),
                );
                let snapshot: Vec<_> = self
                    .world
                    .entities()
                    .map(|(eid, e)| spawn_msg(eid, e))
                    .collect();
                for msg in snapshot {
                    self.send(id, msg);
                }
                let me = spawn_msg(id, self.world.get(id).expect("just spawned"));
                self.broadcast(&me, Some(id));
            }
            Cmd::MoveTo { id, target } => self.world.set_target(id, target),
            Cmd::Leave { id } => self.remove(id),
        }
    }

    fn send(&mut self, to: EntityId, msg: server_msg::Msg) {
        if let Some(tx) = self.clients.get(&to)
            && tx.try_send(ServerMsg { msg: Some(msg) }).is_err()
        {
            self.dead.push(to);
        }
    }

    fn broadcast(&mut self, msg: &server_msg::Msg, skip: Option<EntityId>) {
        for (&id, tx) in &self.clients {
            if Some(id) != skip
                && tx
                    .try_send(ServerMsg {
                        msg: Some(msg.clone()),
                    })
                    .is_err()
            {
                self.dead.push(id);
            }
        }
    }

    fn reap(&mut self) {
        while let Some(id) = self.dead.pop() {
            self.remove(id);
        }
    }

    /// Dropping the client's outbox ends its writer task, which closes the connection.
    fn remove(&mut self, id: EntityId) {
        if self.clients.remove(&id).is_some() {
            self.world.despawn(id);
            self.broadcast(
                &server_msg::Msg::Despawn(pb::EntityDespawn { entity_id: id }),
                None,
            );
        }
    }
}

fn spawn_msg(id: EntityId, e: &Entity) -> server_msg::Msg {
    server_msg::Msg::Spawn(pb::EntitySpawn {
        entity_id: id,
        name: e.name.clone(),
        x: e.pos.x,
        y: e.pos.y,
    })
}

#[cfg(test)]
mod tests {
    use super::clean_name;

    #[test]
    fn names_are_trimmed_and_capped() {
        assert_eq!(clean_name("  alice \n"), "alice");
        assert_eq!(clean_name("a\u{7}b"), "ab");
        assert_eq!(clean_name(""), "player");
        assert_eq!(clean_name(&"x".repeat(100)).len(), 24);
    }
}
