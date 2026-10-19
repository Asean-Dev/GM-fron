# GM

Ragnarok-style MMORPG prototype for mobile and desktop: a **Unity** client and an authoritative **Rust** map server.

New to the project? Read [docs/HANDOFF.md](docs/HANDOFF.md) first (Thai and English): how everything was built, how to run it, and what's next.

| Path | What |
|---|---|
| `proto/game.proto` | Wire protocol. The single source of truth for both sides. |
| `server/crates/map-server` | Tokio TCP map server. One task owns the world and ticks it every 100 ms. |
| `server/crates/protocol` | Rust types generated from `proto/` plus the TCP framing (4-byte big-endian length + protobuf). |
| `server/crates/bot` | Load-test bots that join and click-to-move at random. |
| `server/crates/codegen` | Regenerates the client's C# protocol code. |
| `client/` | Unity 6 project. `Assets/Scripts/Net/GameClient.cs` is the connection; `Assets/Scripts/Game/WorldView.cs` draws entities and sends clicks. |
| `art/` | Town concepts, the Blender town builder, and two three.js pages: the whole-town viewer and the grass test meadow (`python3 art/serve.py`, then http://localhost:8765/). |

## Run it

Needs Rust (via rustup) and Unity 6 LTS (via Unity Hub).

```sh
cd server
cargo run --release -p map-server              # listens on 0.0.0.0:7000
cargo run --release -p bot -- --count 50       # optional: fake players
```

Unity: Unity Hub → **Add → Add project from disk** → pick `client/`. On first open NuGetForUnity restores Google.Protobuf. Open any scene and press **Play**: `WorldView` bootstraps itself, connects to `127.0.0.1:7000`, and you click (or tap) the ground to walk.

## Changing the protocol

Edit `proto/game.proto`, then:

```sh
cd server
cargo build                  # Rust regenerates on build
cargo run -p codegen         # rewrites client/Assets/Scripts/Generated/Game.cs
```

## Tests

```sh
cd server
cargo test --workspace
```

## Next steps

1. Walkability grid per map + A* pathfinding (movement is straight-line today).
2. Area of interest: only send updates for entities near each player (every move is broadcast to everyone today).
3. Monsters and server-side combat.
4. Split into login / char / map servers; persist characters in PostgreSQL.
