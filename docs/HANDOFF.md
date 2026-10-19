# GM: วิธีที่เราทำ และวิธีทำต่อ / How we built it and how to continue

เอกสารนี้สำหรับเพื่อนที่จะมาทำต่อ อ่านจบแล้วควรรันทุกอย่างได้ รู้ว่าแต่ละส่วนทำมายังไง และรู้ว่างานต่อไปคืออะไร
This guide is for whoever picks the project up next. After reading it you should be able to run everything, know how each part was made, and know what comes next.

> งานทั้งหมดอยู่บน branch `prototype/unity-rust-town` ส่วน `main` ยังมีแค่ README จนกว่าจะ merge
> All of this work is on the `prototype/unity-rust-town` branch. `main` only has the README until it's merged.

---

## 1. GM คืออะไร / What GM is

เกม MMORPG สไตล์ Ragnarok เล่นได้ทั้งมือถือและเดสก์ท็อป ฝั่ง client ใช้ **Unity** ฝั่ง server ใช้ **Rust** และ server เป็นคนตัดสินทุกอย่าง (authoritative) เพื่อกันโกง
A Ragnarok-style MMORPG for mobile and desktop. The client is **Unity**, the server is **Rust**, and the server decides every outcome (authoritative) to stop cheating.

| ส่วน / Part | สถานะ / Status |
|---|---|
| Rust map server | ทำงานได้ มีเทสต์ 7 อัน ผ่านหมด รับ bot 200 ตัวได้ / Works; 7 tests pass; handled 200 bots |
| Unity client | เขียนโค้ดแล้ว **แต่ยังไม่เคยเปิดใน Unity** เพราะเครื่องที่ทำไม่มี Unity / Code written but **never opened in Unity**, because the machine it was built on has none |
| Map เมืองเริ่มต้น / Starter-town map | สร้างใน Blender ด้วยสคริปต์ มีตัวดูบนเว็บ / Built in Blender by a script, with a web viewer |
| ทุ่งหญ้าทดลอง / Grass test meadow | หญ้า ลม พายุ ตัวละครเดินแหวกหญ้า ต้นไม้ (เว็บ three.js) / Grass, wind, storm, characters parting the grass, trees (three.js web page) |

## 2. โครงสร้าง repo / Repo layout

| Path | คืออะไร / What it is |
|---|---|
| `proto/game.proto` | รูปแบบข้อความระหว่าง client กับ server ใช้ร่วมกันทั้ง 2 ฝั่ง / The client-server message format, shared by both sides |
| `server/` | Cargo workspace: `map-server`, `protocol`, `bot`, `codegen` |
| `client/` | โปรเจกต์ Unity 6 / The Unity 6 project |
| `art/concepts/` | ภาพ concept เมือง 2 แบบ + prompt ที่ใช้ / Two town concepts + the prompts used |
| `art/tools/build_town.py` | สร้างเมืองใน Blender / Builds the town in Blender |
| `art/tools/export_viewer.py` | export เมืองจาก Blender ไปให้ตัวดูบนเว็บ / Exports the town from Blender for the web viewer |
| `art/maps/town/` | ภาพ render, `walkable.txt`, `town.blend` / Renders, `walkable.txt`, `town.blend` |
| `art/viewer/` | ตัวดูเมืองทั้งเมืองบนเว็บ / Whole-town web viewer |
| `art/meadow/` | ทุ่งหญ้าทดลอง / The grass test meadow |
| `art/serve.py` | เปิดหน้าเว็บใน `art/` บน localhost / Serves the `art/` pages on localhost |

## 3. ต้องลงอะไรบ้าง / What to install

| โปรแกรม / Tool | ใช้ทำอะไร / For | จำเป็นไหม / Needed? |
|---|---|---|
| Rust ผ่าน rustup (ทดสอบกับ 1.94) / Rust via rustup (tested on 1.94) | server | ✔ |
| Unity Hub + Unity 6 LTS | client | ✔ |
| Python 3 | `art/serve.py` | ✔ สำหรับหน้าเว็บ / ✔ for the web pages |
| Blender 5.1 | สร้างหรือแก้ map / Building or editing the map | เฉพาะคนทำ map / Map work only |
| Codex CLI (login แล้ว) / Codex CLI (logged in) | สร้างภาพ concept / Generating concept art | ไม่จำเป็น / Optional |

ไม่ต้องลง protoc เพราะ build ใช้ protoc ที่มากับ crate `protoc-bin-vendored`
You don't need protoc: the build uses the one bundled in the `protoc-bin-vendored` crate.

## 4. วิธีรัน / How to run

```sh
# server (ฟังที่พอร์ต 7000 / listens on port 7000)
cd server
cargo run --release -p map-server

# ผู้เล่นปลอมไว้ทดสอบโหลด / fake players for load testing
cargo run --release -p bot -- --count 50

# เทสต์ / tests
cargo test --workspace

# หน้าเว็บ / web pages: http://localhost:8765/viewer/  http://localhost:8765/meadow/
python3 art/serve.py
```

**Unity:** Unity Hub → Add → Add project from disk → เลือก `client/` ครั้งแรก NuGetForUnity จะโหลด Google.Protobuf ให้ จากนั้นเปิด scene ไหนก็ได้ (เปิด server ไว้ก่อน) แล้วกด Play: `WorldView` จะสร้างตัวเองและต่อ `127.0.0.1:7000` คลิกหรือแตะพื้นเพื่อเดิน
**Unity:** Unity Hub → Add → Add project from disk → pick `client/`. On first open NuGetForUnity restores Google.Protobuf. Start the server, open any scene and press Play: `WorldView` creates itself, connects to `127.0.0.1:7000`, and you click or tap the ground to walk.

> ⚠️ ฝั่ง Unity ยังไม่เคย compile ถ้ามี error ให้แก้ก่อนทำอย่างอื่น และ `ProjectVersion.txt` ใส่ไว้เป็น `6000.3.0f1` ถ้า Hub ฟ้องว่าไม่มี ให้เลือก Unity 6 ที่ลงไว้
> ⚠️ The Unity side has never been compiled. Fix any errors there first. `ProjectVersion.txt` says `6000.3.0f1`; if Hub says it's missing, pick the Unity 6 you have.

## 5. แต่ละส่วนทำมายังไง / How each part was made

### 5.1 เลือก stack / Choosing the stack

- **Unity** เพราะเกมใหญ่ระดับ Ragnarok ต้องลงมือถือกับเดสก์ท็อปได้ดี และ Ragnarok M ก็ใช้ Unity
  **Unity**, because a Ragnarok-sized game needs strong mobile and desktop builds, and Ragnarok M uses Unity.
- **Rust** สำหรับ server เจ้าของโปรเจกต์อยากลอง (ตอนแรกแนะนำ .NET เพราะแชร์โค้ด C# กับ Unity ได้) แต่ server เป็นคนคำนวณ damage อยู่แล้ว เลยเสียเรื่องแชร์โค้ดไม่มาก สิ่งที่ต้องตรงกันคือ `.proto` กับไฟล์ข้อมูลเกม
  **Rust** for the server, because the owner wanted to try it (.NET was the first suggestion, for sharing C# with Unity). The server computes damage anyway, so little is lost; what must match is the `.proto` and the game data files.
- **TCP** เหมือน Ragnarok เพราะเดินแบบคลิกบน grid / **TCP**, like Ragnarok, since movement is click-to-move on a grid.

### 5.2 Protocol

- ทุก frame บน TCP = ความยาว 4 ไบต์แบบ big-endian + ข้อความ protobuf 1 ข้อความ (สูงสุด 64KB)
  Every TCP frame is a 4-byte big-endian length followed by one protobuf message (64KB max).
- Rust ใช้ `prost` (generate ตอน build ใน `server/crates/protocol/build.rs`) ส่วน C# generate ด้วย `cargo run -p codegen` ไปที่ `client/Assets/Scripts/Generated/Game.cs`
  Rust uses `prost` (generated at build time in `server/crates/protocol/build.rs`); C# is generated with `cargo run -p codegen` into `client/Assets/Scripts/Generated/Game.cs`.
- **แก้ `.proto` แล้วต้องรัน `cargo run -p codegen` ทุกครั้ง** และ commit `Game.cs` ด้วย
  **After editing `.proto`, always run `cargo run -p codegen`** and commit `Game.cs`.

### 5.3 Map server

- `world.rs` เป็น logic ล้วน ไม่มี I/O เลยเทสต์ตรงๆ ได้: spawn, ตั้งเป้าหมาย, เดินช่องละ 1 tick (8 ทิศ)
  `world.rs` is pure logic with no I/O, so it's tested directly: spawning, targets, one cell per tick (8 directions).
- `server.rs`: task เดียว (hub) ถือ World และ tick ทุก 100ms ส่วนแต่ละ connection เป็น task ของตัวเอง คุยกับ hub ผ่าน channel จึงไม่ต้องใช้ lock
  `server.rs`: one task (the hub) owns the World and ticks every 100 ms; each connection is its own task talking to the hub over channels, so there are no locks.
- client ที่รับข้อความไม่ทัน (คิวเกิน 4096) จะถูกตัดออก / A client that can't keep up (queue over 4096) gets disconnected.
- ตอนนี้ส่งทุกการเดินให้ทุกคน (ยังไม่มี AOI) และเดินเป็นเส้นตรง (ยังไม่มี A*)
  Right now every move goes to everyone (no AOI yet) and movement is a straight line (no A* yet).

### 5.4 ภาพ concept / Concept art

สร้างด้วย imagegen ของ Codex prompt อยู่ใน `art/concepts/prompt-town-*.txt` ถ้าจะสร้างใหม่:
Made with Codex's imagegen. The prompts are in `art/concepts/prompt-town-*.txt`. To make a new one:

```sh
cd art/concepts
( echo "Use the image generation tool to create ONE image, then save the final PNG to ./concept-town-c.png. Reply with one short line only."; echo; cat prompt-town-c.txt ) \
  | codex exec --skip-git-repo-check -s workspace-write -C . -
```

ใช้เครดิตของบัญชี ChatGPT/Codex ที่ login อยู่ ภาพละประมาณ 2 นาที
It uses the logged-in ChatGPT/Codex account's credits, about 2 minutes per image.

- **A** เมืองแฟนตาซียุโรปแบบนิทาน (map ตอนนี้สร้างจากแบบนี้) / **A** storybook European fantasy town (the current map is built from this)
- **B** เมืองริมคลองแรงบันดาลใจจากไทย / **B** a Thai-inspired canal town
- ⚠️ เจ้าของยังไม่ได้เลือกว่าจะเอาแบบไหน / ⚠️ The owner hasn't picked one yet.

### 5.5 Map เมืองใน Blender / The town map in Blender

เปิด Blender 5.1 → แท็บ Scripting → สร้าง text ใหม่ แล้วรัน (แก้ path ให้ตรงกับเครื่องตัวเอง):
Open Blender 5.1 → Scripting tab → new text, then run (change the path to your clone):

```python
p = "/path/to/GM-fron/art/tools/build_town.py"
exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_town", "__file__": p})
```

- สร้าง scene ชื่อ **"GM Town"** ใช้เวลาประมาณ 90 วินาที และไม่แตะ scene อื่นในไฟล์ รันซ้ำได้ จะสร้างใหม่ทั้งหมด
  Builds a scene called **"GM Town"** in about 90 s and leaves other scenes alone. Rerunning rebuilds it from scratch.
- **1 หน่วยใน Blender = 1 ช่องบน grid ของ server** และ map มีขนาด 100×100 ตรงกับ `MAP_SIZE` ใน `map-server`
  **1 Blender unit = 1 server grid cell**, and the map is 100×100, matching `MAP_SIZE` in `map-server`.
- เขียน `art/maps/town/walkable.txt` ให้ด้วย: `.` หญ้า `=` ถนน `,` ไร่ (เดินได้) / `#` อาคาร กำแพง ต้นไม้ `~` น้ำ (เดินไม่ได้) แถวแรกคือ y=99
  It also writes `art/maps/town/walkable.txt`: `.` grass, `=` road, `,` field (walkable) / `#` building, wall, tree, `~` water (blocked). The first row is y=99.
- ทุกอย่างวางบน grid เดียวกัน: ถนนกับแม่น้ำวาดก่อน แล้วบ้านหาที่ว่างตามถนน (`rect_free` / `claim`)
  Everything is placed on one grid: roads and the river go down first, then houses look for free space along them (`rect_free` / `claim`).
- หญ้าใน Blender เป็น geometry nodes (`GM_Grass`) โรยกอหญ้าแล้วลบจุดที่ทับ `GrassMask` (รอยเท้าแบนๆ ของถนน บ้าน กำแพง) หญ้าแสดงเฉพาะตอน render เพราะถ้าโชว์ใน viewport เครื่องจะกระตุก
  Grass in Blender is geometry nodes (`GM_Grass`): tufts are scattered, and any that land on `GrassMask` (flat footprints of roads, houses, walls) are deleted. Grass only appears in renders, because showing it in the viewport makes the machine crawl.
- render: ตั้งกล้องเป็น `CamOverview` หรือ `CamGameplay` แล้วกด F12 / Renders: set the camera to `CamOverview` or `CamGameplay` and press F12.
- อยากเปลี่ยนเมือง: แก้ค่าด้านบนของสคริปต์ (`PLAZA_R`, `RING_R`, `WALL_R`, `PALETTE`, `SEED`) หรือฟังก์ชัน `house()`, `guild_hall()`, `inn()` ฯลฯ
  To change the town, edit the constants at the top (`PLAZA_R`, `RING_R`, `WALL_R`, `PALETTE`, `SEED`) or functions like `house()`, `guild_hall()`, `inn()`.
- เซฟเป็นไฟล์แยก / Save it as its own file:
  ```python
  bpy.data.libraries.write("/path/to/GM-fron/art/maps/town/town.blend", {bpy.data.scenes["GM Town"]}, fake_user=True, compress=True)
  ```

### 5.6 ตัวดูเมืองบนเว็บ / The town web viewer (`art/viewer/`)

หลังสร้างเมืองใน Blender แล้ว รันสคริปต์นี้เพื่ออัปเดตไฟล์ของตัวดู:
After building the town in Blender, run this to refresh the viewer's files:

```python
p = "/path/to/GM-fron/art/tools/export_viewer.py"
exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_export", "__file__": p})
```

- โมเดล export เป็น glb แบบบีบอัด Draco แล้วแปลงเป็น base64 ใน `town-glb.txt` เพราะที่ host ของ Claude artifact ไม่รับไฟล์ `.glb`
  The model is exported as a Draco-compressed glb, then base64'd into `town-glb.txt`, because the Claude artifact host won't serve `.glb`.
- หน้าเว็บใช้ three.js 0.170 จาก CDN, ถอด Draco ด้วย decoder แบบ JS ใน `draco/`, เปลี่ยน material ถนนและลานเป็น shader หินปูพื้นตามชื่อ material, โรยหญ้าแบบ instanced ตาม `grassmask.png` และอ่านช่อง grid ใต้เมาส์จาก `walkable.txt`
  The page uses three.js 0.170 from a CDN, decodes Draco with the JS decoder in `draco/`, swaps road and plaza materials (by name) for a paving shader, scatters instanced grass using `grassmask.png`, and reads the grid cell under the pointer from `walkable.txt`.
- มีเวอร์ชันที่ publish ไว้: https://claude.ai/artifact/FtrSDGqeKMHq1xvAERha6Z (private เจ้าของต้องกดแชร์ก่อนเพื่อนถึงจะเปิดได้)
  There's a published copy at https://claude.ai/artifact/FtrSDGqeKMHq1xvAERha6Z (private: the owner has to share it before others can open it).

### 5.7 ทุ่งหญ้าทดลอง / The grass test meadow (`art/meadow/index.html`)

เป็นที่ทดลองว่าหญ้า ตัวละคร และต้นไม้จะสวยแค่ไหน ก่อนเอาไปใส่ทั้งเมืองและย้ายไป Unity ทุกอย่างอยู่ในไฟล์เดียว ค้นหาชื่อในตารางเพื่อหาโค้ด
This is where we test how good the grass, characters and trees can look before bringing them to the whole town and porting to Unity. It's all one file; search for the names in the table to find the code.

| เรื่อง / Topic | ค้นหา / Search for | ทำงานยังไง / How it works |
|---|---|---|
| ใบหญ้า / Grass blades | `plantGrass`, `bladeGeometry`, `DENSITY` | ใบเดี่ยว 4 ช่วง วาดแบบ instanced ด้วย shader ของเราเอง 45–140 ใบ/ตร.ม. ความสูงเป็นกลุ่มๆ ตาม noise / Single 4-segment blades, instanced with our own shader, 45–140 per m², heights clumped by noise |
| สีหญ้า / Grass colour | `grassAlbedo` | โคนเข้ม ปลายอ่อน สีเป็นหย่อม ใบละสีต่างกันนิดหน่อย normal ชี้ขึ้นเพื่อให้นุ่มแบบภาพวาด / Dark roots, light tips, colour patches, slight per-blade variation; normals point up for a soft painted look |
| ลมและพายุ / Wind and storm | `gust`, `bendPlant`, `setWind` | noise เลื่อนตามทิศลม ดัดใบตามความสูงยกกำลังสอง แถบ Wind ไปถึง Storm จะทำให้ฟ้ามืด แดดอ่อนลง และเงาเมฆเยอะขึ้น / Noise scrolls with the wind and bends blades by height squared; dragging Wind to Storm darkens the sky, dims the sun and adds cloud shadow |
| เงาเมฆ / Cloud shadows | `cloudShadow` | noise ขนาดใหญ่เลื่อนช้าๆ บังแดดแต่ไม่บังแสงฟ้า / Big slow noise that blocks sun but not sky light |
| ตัวละครแหวกหญ้า / Walkers parting grass | `stampTrample`, `fadeTrample`, `uTrample` | texture ขนาด 256×256 คลุมทุ่ง ทุก frame แต่ละตัวละคร "ปั๊ม" ทิศทางออกจากตัวกับแรงกดลงไป แล้วค่อยๆ จางใน ~2 วินาที shader อ่านแล้วดันใบหญ้าออก / A 256×256 texture over the field; every frame each walker stamps an outward direction and a press strength, which fades in about 2 s; the shader reads it and pushes blades away |
| ตัวละคร / Characters | `makeChibi`, `stepWalker` | chibi ชั่วคราวจากรูปทรงง่ายๆ ท่าเดินแบบ procedural คลิกเพื่อเดิน หลบต้นไม้ด้วยแรงผลัก / Temporary chibi from simple shapes, procedural walk cycle, click to walk, steers around trees with repulsion |
| ต้นไม้ / Trees | `growFoliage`, `broadleaf`, `pine`, `LEAVES` | ใบเป็นแผ่นสี่เหลี่ยมหันหาจอหลายพันแผ่น ตัดเป็นรูปใบด้วย texture ที่วาดใน canvas, normal ชี้ออกจากกลางก้อนให้แสงกลมนุ่ม, ขอบนุ่มด้วย alpha-to-coverage / Thousands of camera-facing leaf cards cut out by a canvas-drawn leaf texture, normals pointing out of each clump for soft round light, soft edges via alpha-to-coverage |
| เงาต้นไม้ / Tree shade | `treeShadow` | วงเงาใต้ต้นไม้ที่มีรูให้แสงลอดเป็นลายจุด / A shadow disc under each tree with holes that let dappled light through |
| มองทะลุใบไม้ / See-through canopy | `uSeeThrough`, `uHero` | ใบที่บังระหว่างกล้องกับฮีโร่จะบางลง (เฉพาะโหมด Follow hero) / Leaves between the camera and the hero thin out (Follow hero mode only) |

ข้อควรรู้ / Things to know:
- tone mapping แบบ AgX ทำให้ใบไม้สีสดดูซีด เราเลยดันความสด (saturation) กลับใน shader ของใบไม้
  AgX tone mapping mutes bright foliage, so the leaf shader pushes saturation back up.
- ทดสอบใน Chromium แบบ headless ได้ (ไม่มี error) แต่เป็น software rendering ภาพเลยหยาบและช้า ให้ดูจริงบนเครื่องที่มี GPU
  It's been tested in headless Chromium (no errors), but that's software rendering, so it looks rough and slow; judge it on a machine with a real GPU.

## 6. ตัวอย่างที่เจ้าของชอบ / References the owner likes

| ตัวอย่าง / Reference | เอามาใช้เรื่อง / Used for |
|---|---|
| [Lands of Koastalia](https://x.com/ValakhP/status/2107942463029882952) | ลุคหมู่บ้านมองจากมุมสูง / The high-angle village look |
| [tkduze: tool wheel](https://x.com/tkduze/status/2111466084243014005) | หญ้าหนาปลายสว่าง, ไถดินปลูกผักบน grid / Dense light-tipped grass, tilling and planting on a grid |
| [tkduze: storm](https://x.com/tkduze/status/2106126079790596560) | หญ้าเหมือนพรม ดอกไม้ส้ม เงาเมฆ พายุ / Carpet-like grass, orange flowers, cloud shadows, storm |
| [Lukas Schneider](https://x.com/zwitscherluki/status/2104934596873703480) | พุ่มใบนุ่มแบบภาพวาด พุ่มดอกสีชมพู / Soft painterly canopies, pink flowering bushes |
| [Unreal world (quoted post)](https://x.com/politicalmath/status/2112052470155477470) | ต้นไม้สูงแตกกิ่ง ใบไม้ร่วงหลายสี ต้นสน / Tall branching trees, multicoloured autumn leaves, pines |

## 7. แผนต่อไป / What's next

**แผนความสวยของหญ้า / Grass beauty plan:**

| ขั้น / Phase | งาน / Work | สถานะ / Status |
|---|---|---|
| 1 | ทุ่งหญ้า: ใบหญ้า สี ลม / Meadow: blades, colour, wind | ✔ |
| 2 | ตัวละคร + คลิกเดิน + กล้องตาม / Character + click-to-move + follow camera | ✔ (เดินเส้นตรง ยังไม่มี A* / straight lines, no A* yet) |
| 3 | หญ้าเอนหลบ + รอยทาง + หลายตัวละคร / Grass bending + trails + several walkers | ✔ |
| 4 | เก็บรายละเอียด / Polish | บางส่วน: มีต้นไม้แล้ว ยังไม่มีฝน แสงลอด (god rays) และเศษหญ้าปลิว / Partly: trees done; rain, god rays and kicked-up grass still to do |
| 5 | เอาหญ้าและต้นไม้แบบทุ่งทดลองไปใส่ทั้งเมือง + ตั้งค่าคุณภาพ + ทดสอบมือถือ / Bring the meadow's grass and trees to the whole town + quality presets + phone test | ยังไม่เริ่ม / Not started |
| 6 | ย้ายไป Unity (GPU indirect instancing, compute culling, shader ใน URP) / Port to Unity (GPU indirect instancing, compute culling, URP shaders) | ยังไม่เริ่ม / Not started |

**Server:**
1. ให้ server โหลด `walkable.txt` แล้วหาทางด้วย A* / Load `walkable.txt` on the server and pathfind with A*.
2. AOI: ส่งข้อมูลเฉพาะสิ่งที่อยู่ใกล้ผู้เล่น / AOI: only send updates for things near each player.
3. มอนสเตอร์และการต่อสู้ฝั่ง server / Monsters and server-side combat.
4. แยกเป็น login / char / map server และเก็บตัวละครใน PostgreSQL / Split into login / char / map servers; store characters in PostgreSQL.

**รอเจ้าของตัดสินใจ / Waiting on the owner:**
1. เอา concept A หรือ B / Concept A or B.
2. จะมีระบบให้ผู้เล่นสร้างเอง (วงล้อเครื่องมือ ถางหญ้า ไถดิน วางบ้าน แบบ tkduze) ไหม / Whether players get a building system (tool wheel, cutting grass, tilling, placing houses, like tkduze).
3. ตัวละครจริงจะใช้ตัวไหน (chibi ชั่วคราว หรือตัว Hero ในไฟล์ Blender ของเจ้าของ) / Which character model to use (the temporary chibi, or the Hero in the owner's Blender file).

## 8. เรื่องที่อาจเจอ / Gotchas

- ระบบพิกัด: ช่อง (x, y) = Blender (x, y) = three.js (x, 0, -y) ตอนเอาโมเดลเข้า Unity ต้องเช็คทิศแกนอีกที เพราะ glTF กับ Unity ใช้แกนต่างกัน
  Coordinates: cell (x, y) = Blender (x, y) = three.js (x, 0, -y). When the model goes into Unity, double-check the axes, since glTF and Unity use different conventions.
- material ที่เป็น procedural ใน Blender (หญ้า หินปูพื้น) export ออกไปไม่ได้ ตัวดูบนเว็บจึงสร้าง shader ใหม่เองตามชื่อ material ถ้าจะเอาเข้า Unity ต้อง bake เป็น texture หรือเขียน shader ใหม่
  Procedural Blender materials (grass, paving) don't export, so the web viewer rebuilds them as shaders by material name. For Unity, bake them to textures or write new shaders.
- `art/viewer/town.glb` ถูก ignore ใน git เพราะ generate ใหม่ได้ ตัวดูใช้ `town-glb.txt`
  `art/viewer/town.glb` is git-ignored because it's regenerated; the viewer uses `town-glb.txt`.
- ถ้า Blender กระตุก ให้ดูว่า viewport ไม่ได้อยู่ในโหมด Rendered
  If Blender lags, make sure the viewport isn't in Rendered mode.
