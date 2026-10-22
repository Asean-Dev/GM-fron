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
| `art/beach/` | ฉากชายหาด 3D ที่ render เป็นพิกเซล / A 3D beach rendered as pixel art |
| `art/models/horse/` | ม้าตัวจริงสำหรับเกม: model sheet, texture, `horse.glb` / The game-ready horse: model sheet, textures, `horse.glb` |
| `art/horse/` | หน้าดูโมเดลม้าและท่าทาง / Horse model and animation viewer |
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

# หน้าเว็บ / web pages: http://localhost:8765/viewer/  /meadow/  /beach/
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
| แสงและท้องฟ้า / Light and sky | `LOOKS`, `setLook`, `skyDome`, `lightModels` | สวิตช์ Light ในแผงมี 2 แบบ: **Golden hour** (ค่าเริ่มต้น สีตามคลิป Tree Damage: ฟ้าม่วงไล่เป็นชมพูที่ขอบฟ้า แดดสีทอง เงาสีม่วงอ่อน หญ้าสีทอง เมฆขาวอมชมพู) และ **Day** (แบบเดิม) แต่ละแบบกำหนดสีฟ้า เมฆ แดด เงา แสงบนโมเดล หญ้า และหมอกไว้ใน `LOOKS` ท้องฟ้าเป็นโดมรอบกล้องที่มีเมฆลอยตามลม (พายุมีเมฆมากขึ้นและเป็นสีเทา) กล้องก้มต่ำได้เกือบระดับพื้นเพื่อให้เห็นท้องฟ้า (`maxPolarAngle`) / The Light switch in the panel has two looks: **Golden hour** (the default, coloured like the Tree Damage reel: a violet sky fading to pink at the horizon, golden sun, lavender shade, golden grass, white-pink clouds) and **Day** (the old look). Each sets the sky, clouds, sun, shade, model lights, grass and haze in `LOOKS`. The sky is a dome round the camera with clouds drifting on the wind (more and greyer in a storm), and the camera can tilt down to almost ground level to see it (`maxPolarAngle`) |
| เงาเมฆ / Cloud shadows | `cloudShadow` | noise ขนาดใหญ่เลื่อนช้าๆ บังแดดแต่ไม่บังแสงฟ้า / Big slow noise that blocks sun but not sky light |
| ตัวละครแหวกหญ้า / Walkers parting grass | `stampTrample`, `fadeTrample`, `uTrample` | texture ขนาด 256×256 คลุมทุ่ง ทุก frame แต่ละตัวละคร "ปั๊ม" ทิศทางออกจากตัวกับแรงกดลงไป แล้วค่อยๆ จางใน ~2 วินาที shader อ่านแล้วดันใบหญ้าออก / A 256×256 texture over the field; every frame each walker stamps an outward direction and a press strength, which fades in about 2 s; the shader reads it and pushes blades away |
| ตัวละคร / Characters | `makeChibi`, `stepWalker` | chibi ชั่วคราวจากรูปทรงง่ายๆ ท่าเดินแบบ procedural คลิกเพื่อเดิน หลบต้นไม้ด้วยแรงผลัก / Temporary chibi from simple shapes, procedural walk cycle, click to walk, steers around trees with repulsion |
| ต้นไม้ฉากหลัง / Backdrop trees | `growFoliage`, `broadleaf`, `birch`, `pine`, `leafAtlas`, `PALETTES` | ใบเป็นแผ่นสี่เหลี่ยมหันหาจอหลายพันแผ่น ตัดเป็นรูปใบด้วย atlas 4×2 ที่วาดใน canvas (ใบแหลม ใบโอ๊ก ใบเบิร์ช ใบเฟิร์น ใบสน) normal ชี้ออกจากกลางก้อนให้แสงกลมนุ่ม ขอบนุ่มด้วย alpha-to-coverage สีใบไล่จากเงาไปขอบตาม palette (ด้านล่างและข้างในเข้ม ด้านบนสว่าง) และแดดลอดใบตอนมองย้อนแสง กิ่งเป็นท่อโค้งรวมเป็น mesh เดียวต่อวัสดุ (`limbGeometry`) สีป่าวงนอกตามโซนที่อยู่ติดกัน ต้นสนเป็นทรงกรวยจากชั้นใบที่ห้อยลง ขอบชั้นสว่าง ข้างในและใต้ชั้นมืด (`pine`, `addSkirt`) / Thousands of camera-facing leaf cards cut out by a canvas-drawn 4×2 atlas (pointed, oak, birch, fern, needles), normals pointing out of each clump for soft round light, soft edges via alpha-to-coverage. Leaf colour runs shadow → rim along a palette (underside and inside dark, top bright), and the sun glows through the leaves when you look toward it. Limbs are curved tubes merged into one mesh per material (`limbGeometry`); the outer forest takes the colours of the grove beside it. Pines are fir cones of drooping needle tiers, bright at each tier's rim and dark inside and underneath (`pine`, `addSkirt`) |
| เงาต้นไม้ / Tree shade | `treeShadow` | วงเงาใต้ต้นไม้ที่มีรูให้แสงลอดเป็นลายจุด / A shadow disc under each tree with holes that let dappled light through |
| ทะเลสาบ / Lake | `lakeDistance`, `groundHeight`, `lake` | รูปทะเลสาบเป็นฟังก์ชันเดียวทั้งใน JS และ shader พื้นยุบลงเป็นแอ่ง มีหาดทราย น้ำใช้ Reflector สะท้อนภาพจริง สีไล่ตามความลึก ฟองซัดขอบ น้ำขึ้นลงเบาๆ ตอนพายุมีคลื่นหัวขาว หญ้าอยู่ layer 1 เพื่อไม่ต้อง render ซ้ำในเงาสะท้อน / The lake shape is one function in JS and the shaders; the ground dips into a basin with a sandy beach; the water uses a Reflector for real reflections, colour by depth, foam washing the edge, a gentle tide, and whitecaps in a storm; grass sits on layer 1 so the reflection skips it |
| สัตว์ขี่และสัตว์เลี้ยง / Mounts and pet | `mounts`, `stepMount`, `driveModel`, `makeSprings`, `poseRider`, `toggleRide`, `pet`, `stepPet` | สัตว์ขี่สามตัวใช้ระบบเดียวกัน: ม้า (`art/models/horse/generated/horse.glb`), นกสายฟ้า (`art/models/biped/generated/thunder.glb`) และงูโคมไฟ (`art/models/serpent/generated/serpent.glb`) แต่ละตัวมีค่าใน `cfg` (ท่าเดินกับท่าเร็ว ความเร็ว ความลึกที่ลุยน้ำได้ ความสูงที่นั่ง กระดูกที่คนขี่นั่ง spring ของหาง/ขน/หนวด) งูว่ายข้ามทะเลสาบได้เต็มความเร็วและลอยบนน้ำลึก (`float`) คลิกตัวไหนก็ขึ้นขี่ตัวนั้น แล้วคลิกพื้นเพื่อไป ลูกงู (`serpent-baby.glb`) เป็นสัตว์เลี้ยงที่ว่ายตามตัวละคร หรือตามสัตว์ขี่ตอนขี่อยู่ ท่าเล่นเร็วขึ้นได้ถึง 7 เท่าเพื่อให้ตามทัน (`maxRate`) งูวัยรุ่น (`serpent-teen.glb`, 2.5 ม.) และงูแก่ (`serpent-elder.glb`, 6 ม.) เดินเล่นเองริมทะเลสาบ (`wild`, `teen`, `elder`) ขี่ไม่ได้เพราะมีอานแค่วัยโต คลิกแล้วขึ้นข้อความบอก / Three mounts share one system: the horse (`art/models/horse/generated/horse.glb`), the Thunder Runner (`art/models/biped/generated/thunder.glb`) and the Lantern Serpent (`art/models/serpent/generated/serpent.glb`). Each has its own `cfg` (walk and fast clips, speeds, how deep it wades, seat height and bone, tail/feather/antenna springs); the serpent swims across the lake at full speed and floats on deep water (`float`). Click any of them to mount it, then click the ground to go there. The baby serpent (`serpent-baby.glb`) is a pet that swims after the hero, or after the mount being ridden, playing its clips up to 7× faster to keep up (`maxRate`). The teen (`serpent-teen.glb`, 2.5 m) and the elder (`serpent-elder.glb`, 6 m) roam the lake shore on their own (`wild`, `teen`, `elder`); only the adult has a saddle, so they can't be ridden, and clicking one shows a note |
| เอฟเฟกต์ตอนเคลื่อนที่ / Travel effects | `travelFx`, `stepFx`, `surfaceAt`, `fxPlain`, `fxGlow` | ทุกตัวที่เคลื่อนที่ (ตัวละคร คนเดิน สัตว์ขี่ สัตว์เลี้ยง) เตะของขึ้นจากพื้นที่เหยียบ: หญ้า = เศษใบหญ้า กลีบดอกส้มขาว และละอองเกสร, น้ำ = ละอองน้ำกระเด็นและคลื่นรูปตัว V ตามหลัง, ทางเดินกับทราย = ฝุ่น งูกดหญ้าและกวนน้ำตลอดลำตัว (ใช้แผนที่เหยียบหญ้าเดียวกัน) และงูโคมไฟปล่อยละอองเรืองแสงจากตัวและโคม อนุภาคอยู่ในกลุ่มจุดสองชุด (ปกติ และเรืองแสงแบบบวกสี) สูงสุดชุดละ 1,200 จุด ปิดเองถ้าผู้ใช้ตั้ง reduce motion ทดสอบแบบ headless ใช้ `gmAdvance(วินาที)` เดินโลกที่ 60 fps โดยไม่วาด และ `gmCamera(pos, target)` / Everything that moves (hero, walkers, mounts, pet) kicks up the ground it crosses: grass = blade bits, orange and white petals and pollen; water = splash droplets and a V of ripples behind; path and sand = dust. Serpents press the grass and churn the water along their whole body (the same trample map), and the lantern serpents shed glowing motes from the body and lanterns. Particles live in two point clouds (plain, and additive glow) of up to 1,200 each; off when the user prefers reduced motion. For headless checks, `gmAdvance(seconds)` steps the world at 60 fps without drawing, and `gmCamera(pos, target)` places the camera |
| ต้นไม้ที่ตัดได้ / Choppable trees and woodcutting | `TREES`, `GROW`, `buildTree`, `plantTree`, `zoneAt`, `GROVES`, `clickTree`, `stepChopper`, `chopHit`, `breakTree`, `stepLogs`, `pickUp`, `stepWoodland`, `stepBirds`, `impactFrame` | ทุ่งแบ่งเป็น 3 โซนเหมือนเกมที่จะมีหลายโซน (`zoneAt`): โอ๊กใบแดงกับต้นทรงชั้นด้าน -x (แบบคลิป Tree Damage), ป่าเบิร์ชเปลือกขาวใบฟ้าอมเขียวด้าน -z และต้นจามจุรีรอบทะเลสาบ แต่ละชนิดสร้างจาก seed ด้วยโค้ดใน `GROW` (seed เดียวกันได้ต้นเดียวกันเสมอ) ค่าของแต่ละชนิดอยู่ใน `TREES`: จำนวนครั้งที่ฟัน (โอ๊ก 6, ทรงชั้น 4, เบิร์ช 3, จามจุรี 5), จำนวนท่อนไม้และไม้ต่อท่อน, palette, มุมที่ล้มลง แต่ละต้นเป็นวัตถุแยก (ตอ + ส่วนบน) คลิกต้นไม้ 1 ครั้ง = ฟันขวาน 1 ที ทุกทีมี impact frame ทีสุดท้ายต้นไม้ล้มด้วยฟิสิกส์บานพับที่ตอ แล้วลำต้นแตกเป็นท่อนไม้ที่**วางอยู่บนพื้น** เดินไปใกล้แล้วกดปุ่ม Pick Up (หรือ E) หรือคลิกท่อนไม้ให้เดินไปเก็บ ฮีโร่ยกท่อนไม้ขึ้นเหนือหัวแล้วได้ไม้ (ตัวนับในแผง) ตอเหลือ 40 วินาทีแล้วโตใหม่เป็นชนิดเดิมในรูปทรงใหม่ (`WOODLAND`) นก ใบร่วงตามสีของต้น และต้นไม้ไหวเมื่อมีคนผ่านยังทำงานเหมือนเดิม ลำต้นมีสันนูนที่ขยายเป็นรากค้ำตรงโคน (`trunkLobes`) ตอใช้รูปหน้าตัดเดียวกับลำต้นจึงต่อกันสนิทตรงรอยตัด (`stumpGeometry`) ลำต้นโอ๊กกับจามจุรีโค้งมนเป็นโดมตรงจุดแตกกิ่งแล้วกิ่งงอกออกจากโดม (`forkTaper`) ลายเปลือกไม้ต่อกันไม่มีรอยต่อ และเข้มขึ้นเมื่อใกล้พื้น การสร้างบ้านพักไว้ก่อน / The meadow has three zones, as the game will (`zoneAt`): red autumn oaks and tiered trees on the -x side (like the Tree Damage reel), a white-bark birch wood with teal leaves toward -z, and silk trees round the lake. Every tree grows from a seed in code (`GROW`), so the same seed always gives the same tree. Per-species settings live in `TREES`: hits to fell (oak 6, tiered 4, birch 3, silk 5), logs and wood per log, palettes, and the angle it lands at. Each tree is its own object (stump + everything above). One click on a tree = one axe swing; every hit has an impact frame. The last hit topples the tree with hinge physics at the stump, and the trunk breaks into logs that **lie on the ground**: walk up and press Pick Up (or E), or click a log to walk over and grab it. The hero lifts it overhead and gets its wood (counted in the panel). The stump stays 40 s, then regrows as the same species in a new shape (`WOODLAND`). Birds, leaves falling in the tree's own colours, and rustling when someone brushes past work as before. Trunks have ridges that swell into buttress roots at the base (`trunkLobes`); the stump continues the same outline, so it meets the trunk without a step at the cut (`stumpGeometry`); oak and silk trunks round off in a dome where they split and the limbs grow out of it (`forkTaper`); the bark tiles without seams and darkens toward the ground. House building is on hold |
| ถางพื้นที่และแปลงสร้างบ้าน / Land clearing and building plots | `LAND`, `clearLand`, `levelLand`, `stepLand`, `JOB`, `stepJob`, `queueCut`, `digHit`, `cellState`, `placePlot`, `workPlot`, `setMode` | แถบล่างจอมี 3 โหมด: **Walk** (เดิน ฟันต้นไม้ คลิกตอเพื่อขุด), **Clear** (ลากบนหญ้าเพื่อสั่งถาง ฮีโร่ทำตามคิวทีละจุด พุ่มไม้ฟัน 2 ที) และ **Plot** (วางแปลง 4×4 / 6×6 / 8×8 ช่อง ช่องละ 1 ม.) เครื่องมือเลือกเองตามงาน: ขวาน พลั่ว เคียว คราด (`TOOLS`) **Land map** เป็น texture 256×256 คลุมทุ่ง: r = หญ้าโตแค่ไหน, g = ปรับพื้นแล้ว, b = ดินเปียก shader หญ้าให้ใบที่โตไม่ถึงเกณฑ์ของตัวเองหายไป หญ้าที่ขึ้นใหม่จึงเป็นต้นอ่อนห่างๆ ก่อนแล้วค่อยแน่น พื้นเปลี่ยนเป็นดิน (ขุดใหม่สีเข้ม, ปรับแล้วสีอ่อนเรียบ) หญ้าที่ถางแล้วรอ 30 วิ. แล้วค่อยๆ ลามกลับจากขอบ (ประมาณ 5 นาทีสำหรับวงกว้าง 3 ม.) ดอกไม้กลับมาทีหลังสุด พื้นที่ปรับแล้ว**ไม่มีหญ้าขึ้น** ขุดตอแล้วต้นไม่โตอีก ส่วนตอในแปลงจะรอให้ขุด แปลงแสดงสีทุกช่อง: แดง = สร้างไม่ได้, ส้ม = มีต้นไม้/ตอ, เหลือง = มีหญ้า/พุ่ม, เขียว = พร้อมปรับ ปุ่ม **Work on plot** สั่งขุดตอ ถาง และปรับพื้นให้ครบ (ต้นที่ยังยืนต้องฟันเอง) ครบทุกช่องแล้วขึ้นป้าย READY TO BUILD ถ้าลบแปลง (✕) หญ้าจะค่อยๆ กลับมา ทดสอบ headless: `gmClear`, `gmLand`, `gmCut`, `gmPlot`, `gmWorkPlot`, `gmPlots`, `gmJobs` / A dock along the bottom has three modes: **Walk** (walk, chop, click a stump to dig it out), **Clear** (drag over grass to queue cutting; the hero works through it spot by spot; bushes take 2 cuts) and **Plot** (stake out 4×4 / 6×6 / 8×8 cells, 1 m each). The tool follows the job: axe, shovel, sickle, rake (`TOOLS`). The **land map** is a 256×256 texture over the field: r = grass growth, g = levelled, b = soil wetness. The grass shader drops blades whose own threshold the growth hasn't reached, so regrowth starts as sparse sprouts and fills in; the ground turns to soil (dark when freshly dug, pale and smooth when levelled). Cut grass waits 30 s, then creeps back in from the edges (about 5 min for a 3 m patch); flowers return last; levelled ground **never regrows**. A dug-out stump never regrows, and stumps on a plot wait to be dug. Plot cells are coloured: red can't be built on, orange has a tree or stump, yellow grass or a bush, green is ready to level. **Work on plot** queues digging, cutting and levelling (standing trees you chop yourself); when every cell is levelled a READY TO BUILD sign goes up. Removing a plot (✕) lets the grass take it back. Headless hooks: `gmClear`, `gmLand`, `gmCut`, `gmPlot`, `gmWorkPlot`, `gmPlots`, `gmJobs` |
| มองทะลุใบไม้ / See-through canopy | `uSeeThrough`, `uHero` | ใบที่บังระหว่างกล้องกับฮีโร่จะบางลง (เฉพาะโหมด Follow hero) / Leaves between the camera and the hero thin out (Follow hero mode only) |

ข้อควรรู้ / Things to know:
- tone mapping แบบ AgX ทำให้ใบไม้สีสดดูซีด เราเลยดันความสด (saturation) กลับใน shader ของใบไม้
  AgX tone mapping mutes bright foliage, so the leaf shader pushes saturation back up.
- ทดสอบใน Chromium แบบ headless ได้ (ไม่มี error) แต่เป็น software rendering ภาพเลยหยาบและช้า ให้ดูจริงบนเครื่องที่มี GPU
  It's been tested in headless Chromium (no errors), but that's software rendering, so it looks rough and slow; judge it on a machine with a real GPU.

### 5.8 ชายหาดพิกเซล / The pixel beach (`art/beach/index.html`)

ฉาก 3D จริง (ทราย น้ำ ปาล์ม ตู้กดน้ำ เสาไฟ ตัวละคร) ที่ render ลง texture ความละเอียดต่ำ แล้วขยายแบบไม่เบลอให้เห็นเป็นพิกเซล พร้อมลดจำนวนสีและ dither แบบ Bayer
A real 3D scene (sand, water, palms, vending machines, a lamp post, the hero) rendered into a low-resolution target, then scaled up without blur so it reads as pixels, with a reduced palette and Bayer dithering.

| เรื่อง / Topic | ค้นหา / Search for | ทำงานยังไง / How it works |
|---|---|---|
| พิกเซล / Pixels | `lowRes`, `post`, `setPixel` | render ที่ 1/2–1/4 ของจอ แล้วขยายแบบ nearest / Render at 1/2 to 1/4 of the screen, then scale up with nearest filtering |
| รูปทรงหาด / Beach shape | `heightAt`, `HEIGHT_GLSL` | ฟังก์ชันความสูงเดียวกันทั้งใน JS และ shader น้ำ เลยรู้ความลึกทุกจุด / The same height function in JS and the water shader, so depth is known everywhere |
| น้ำ / Water | `Reflector`, `waterUniforms` | สะท้อนภาพจริง, สีไล่ตามความลึก, ฟองตรงขอบและคลื่นที่ม้วนเข้าฝั่ง, น้ำขึ้นลงเบาๆ (`tide`), แสงวิบวับตอนกลางวัน / Real reflections, colour by depth, foam at the edge and rolling in, a gentle tide (`tide`), daytime glints |
| กลางวัน-กลางคืน / Day-night | `SKY`, `setTime` | ไล่สีฟ้าและแสงตามชั่วโมง พระอาทิตย์เคลื่อนจากตะวันออกไปตะวันตก กลางคืนกลายเป็นแสงจันทร์ เสาไฟสีชมพูเปิดตอนค่ำและทำเงาจริง / Sky and light follow the hour, the sun arcs east to west and becomes moonlight at night, and the pink lamp switches on at dusk with real shadows |

อ้างอิงจากเกม Flavour Edge ([reel](https://www.instagram.com/reel/DegQXXYB1Bf/)) / Based on the game Flavour Edge ([reel](https://www.instagram.com/reel/DegQXXYB1Bf/)).

### 5.9 ม้าตัวจริงสำหรับเกม / The game-ready horse (`art/models/horse/`)

ออกแบบเป็น model sheet ด้วย Codex imagegen (`model-sheet-horse-v1.png`) แล้วปั้นใน Blender ด้วยสคริปต์ ไม่ใช้ Meshy:
Designed as a model sheet with Codex imagegen (`model-sheet-horse-v1.png`), then built in Blender by script, without Meshy:

```python
p = "/path/to/GM-fron/art/tools/build_horse.py"
exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_horse", "__file__": p})
```

| ขั้น / Step | ทำอะไร / What it does |
|---|---|
| model | ต่อรูปทรงเป็นตัวม้า แล้ว voxel remesh + smooth + decimate ให้เป็น mesh ชิ้นเดียวเนียนๆ ลงสีด้วย vertex colour (ขาเข้ม จมูกครีม แถบขาวหน้า) / Shapes fused by voxel remesh + smooth + decimate into one smooth mesh, coloured by vertex colour (dark socks, cream muzzle, blaze) |
| texture | คลี่ UV แล้ว bake สี x texture ภาพวาดจาก Codex (`textures/tex-*.png`) x เงานุ่ม ลงเป็น `horse-body.png`, `horse-mane.png`, `horse-tail.png`, `horse-tack.png`, `horse-headgear.png` / UV unwrap, then bake colour x painted Codex textures x soft occlusion into those PNGs |
| rig | กระดูก 24 ชิ้น, ตัว/แผงคอ/หาง/สายจูงใช้ automatic weights, อานกับบังเหียนติดกระดูกแบบแข็ง, ท่า Idle / Graze / Walk / Gallop / 24 bones; body, mane, tail and reins use automatic weights; saddle and bridle ride rigidly on bones; Idle / Graze / Walk / Gallop actions |
| export | `horse.glb` (ประมาณ 14,500 สามเหลี่ยม, texture ฝังในไฟล์, หันหน้า +Z) และ `horse.blend` / `horse.glb` (about 14,500 triangles, textures embedded, facing +Z) and `horse.blend` |

ดูโมเดลกับท่าทางได้ที่ http://localhost:8765/horse/ / View the model and its animations at http://localhost:8765/horse/.

**ม้าจาก Hyper3D (ตัวที่เหมือน sheet ที่สุด) / The Hyper3D horse (closest to the sheet):** `art/models/horse/generated/horse.glb`
1. ใน Blender เปิด Hyper3D Rodin ในแผง MCP for Blender แล้วสร้างจากภาพเดียว `rodin-input/three-quarter.png` **ห้ามใส่ bbox** (ใส่แล้ว AI ยืดตัวและเติมแผ่นแปลกๆ ด้านข้าง) และหลายมุมพร้อมกันก็ได้ผลแย่กว่าภาพเดียว
   In Blender, enable Hyper3D Rodin in the MCP for Blender panel and generate from the single image `rodin-input/three-quarter.png`. **Don't pass a bbox** (it stretched the model and filled it with stray slabs), and several views at once came out worse than one.
2. นำเข้าแล้วรัน `art/tools/rig_generated_horse.py` (SOURCE = ชื่อ object ที่นำเข้า): หันหน้า ย่อให้สูง 1.49 ม. ลดเหลือ 14,000 สามเหลี่ยม วัดตำแหน่งขา หัว หาง แล้ววางกระดูกชุดเดียวกับตัวที่ปั้นด้วยสคริปต์ ใส่น้ำหนักผ่านร่างตัวแทนที่ปิดสนิท (เพราะ Bone Heat ใช้กับ mesh จาก AI ไม่ได้) แล้วใส่ 4 ท่าและ export
   Import, then run `art/tools/rig_generated_horse.py` (SOURCE = the imported object's name): it orients, scales to 1.49 m, decimates to 14,000 triangles, measures the legs, head and tail to fit the same skeleton as the scripted horse, weights it through a watertight proxy (Bone Heat fails on AI meshes), adds the 4 actions and exports.
3. หน้าดูโมเดล `art/horse/` ให้ม้าเดินหรือวิ่งวนรอบเวทีด้วยความเร็วที่ตรงกับก้าว (Walk 1.35 ม./วิ., Gallop 5 ม./วิ.) และมี physics หางแบบ spring bone (ค้นหา `stepTail`): ปลายกระดูกหางแต่ละท่อนมีแรงเฉื่อย ถูกดึงกลับหาท่าจาก animation และหย่อนตามแรงโน้มถ่วง ใน Unity ให้ใช้ spring/dynamic bone แบบเดียวกันกับกระดูก tail1–tail3
   The viewer `art/horse/` walks or gallops the horse round the stage at speeds matching the stride (Walk 1.35 m/s, Gallop 5 m/s) and runs spring-bone tail physics (search `stepTail`): each tail bone's tip keeps momentum, is pulled back toward the animated pose, and sags under gravity. In Unity, use the same kind of spring/dynamic bone on tail1–tail3.
4. จุดที่ยังไม่สวย: ใต้ท้องมีสีซีดเป็นแนวตรง และโกลนมีสีพื้นหลังติดอยู่ เพราะ AI เดาส่วนที่ภาพไม่เห็น
   Known flaws: a pale straight-edged patch under the belly, and background colour inside the stirrups, where the AI guessed parts the image didn't show.

### 5.10 นกสายฟ้า (สัตว์ขี่ 2 ขา) / The Thunder Plume Runner, a two-legged mount (`art/models/biped/`)

เจ้าของเลือกตัวที่ 4 จาก `concept-lineup-biped-v2.png` แล้วทำ model sheet `model-sheet-thunder-v1.png` (หงอนสูงประมาณ 1.95 ม.) ด้วย Codex จากนั้นทำแบบเดียวกับม้า Hyper3D:
The owner picked #4 from `concept-lineup-biped-v2.png`; Codex drew the model sheet `model-sheet-thunder-v1.png` (crest about 1.95 m). Then the same path as the Hyper3D horse:

1. สร้างด้วย Hyper3D จากภาพเดียว `rodin-input/three-quarter.png` (ตัดมุม 3/4 จาก sheet ไม่ใส่ bbox) แล้วนำเข้าชื่อ `RodinThunder`
   Generate with Hyper3D from the single image `rodin-input/three-quarter.png` (the sheet's 3/4 view, no bbox) and import it as `RodinThunder`.
2. รัน `art/tools/rig_biped.py` / Run `art/tools/rig_biped.py`:
   ```python
   p = "/path/to/GM-fron/art/tools/rig_biped.py"
   exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_biped", "__file__": p, "SOURCE": "RodinThunder"})
   ```
   - ลบเท้าผี: AI เดาขาที่มองไม่เห็นแล้วเติมเท้าลอยเกินมาข้างละอัน กับตอขาที่สามห้อยใต้ท้อง สคริปต์เชื่อมรอยต่อ UV ให้เป็นชิ้นเดียว ลบชิ้นที่หลุด แล้วลบส่วนใต้ท้องที่ไม่อยู่ตามแนวขาจริงและปิดรู
     Ghost removal: guessing the hidden leg, the AI added a loose extra foot on each side and a third-leg stump under the belly. The script welds UV seams into one piece, deletes the loose pieces, then deletes whatever under the belly isn't along a real leg and caps the hole.
   - วัดแนวขาแต่ละข้างจากข้อเท้าขึ้นไป (สองขายืนไม่เท่ากัน) แขน และขนหาง แล้ววางกระดูก 2 ขา 41 ชิ้น: ขา (thigh/shin/foot/toe) แขน หงอน 3 สาย หาง 3 สาย (บน กลาง ล่าง ตามพู่หางที่ตั้งขึ้น) และขนแขน
     Measures each leg's centre line from the ankle up (the two legs stand differently), the arms and the tail plume, then places a 41-bone biped rig: legs (thigh/shin/foot/toe), arms, three crest chains, three tail chains (upper, middle, lower, following the upright plume) and arm feathers.
   - สะท้อนครึ่งซ้ายไปทางขวา (`symmetrize`) เพราะ AI ปั้นตัวในท่าก้าวขา สองขาจึงไม่เหมือนกัน (อานข้างขวาจะได้ลายกลับด้านของข้างซ้าย)
     Mirrors the left half onto the right (`symmetrize`): the AI built it mid-stride, so the two legs differed (the right saddle flap now shows the left one's decoration, mirrored).
   - ใส่น้ำหนักผ่านร่างตัวแทนเหมือนม้า (ทำให้หนาด้วย Solidify ก่อน remesh ไม่งั้นตัวหายเหลือแต่กรงเล็บ) จำกัดระยะของกระดูกแขนขา (`LIMB_REACH`) ให้ฝ่าเท้าติดกระดูกนิ้วทั้งแผ่น และตัดเหลือ 4 กระดูกต่อจุดให้ตรงกับ glTF
     Weights go through a proxy like the horse (thickened with Solidify before the remesh, otherwise the body vanishes and only the claws remain), limb bones are limited in reach (`LIMB_REACH`), the foot pad rides the toe bone as one piece, and each vertex keeps its 4 strongest bones to match glTF.
   - ท่า Walk / Run ใช้ foot IK (`GAITS`, `solve_leg`): เท้าที่แตะพื้นไม่ไถล ส้นเท้ายกก่อนถีบ นิ้วงอตอนยกขา ตัวโน้มไปหน้าตอนวิ่ง หัวนิ่งระดับ และหัวผงกแบบนกตอนเดิน ความเร็วที่ตรงกับก้าว: Walk 1.09 ม./วิ., Run 3.75 ม./วิ. แล้ว export `generated/thunder.glb` (ประมาณ 13,800 สามเหลี่ยม)
     Walk / Run are keyed with foot IK (`GAITS`, `solve_leg`): planted feet don't slide, the heel peels before push-off, toes curl in the air, the body leans into the run with the head kept level, and the walk has a bird head-bob. Matching ground speeds: Walk 1.09 m/s, Run 3.75 m/s. Exports `generated/thunder.glb` (about 13,800 triangles).
   - ต้องเชื่อมรอยต่อ UV ก่อนลดจำนวนสามเหลี่ยม (`weld` ใน `rig_generated_horse.py`) เพราะ Hyper3D แยก mesh เป็นชิ้นตามรอย UV ถ้าลดก่อน แต่ละชิ้นจะถูกลดแยกกัน รอยต่อไม่ตรงกัน ผิวเลยแตกเป็นรู (เคยมีรอยเปิด 6,315 เส้น ตอนนี้เหลือ 11)
     Join the UV-seam pieces before reducing triangles (`weld` in `rig_generated_horse.py`): Hyper3D splits the mesh into pieces along its UV seams, and reduced piece by piece the seams stop lining up and the surface cracks open (it had 6,315 open edges; now 11).
3. ดูได้ที่ http://localhost:8765/horse/?model=thunder มี physics ขนแบบ spring bone ที่หงอน หาง และขนแขน (ดู `MODELS.thunder.chains` ใน `art/horse/index.html`; ชุดเดียวกันอยู่ใน `FEATHER_CHAINS` ของสคริปต์ ใช้ตั้งค่า dynamic bone ใน Unity)
   View it at http://localhost:8765/horse/?model=thunder, with spring-bone feather physics on the crest, tail and arm feathers (see `MODELS.thunder.chains` in `art/horse/index.html`; the same list is `FEATHER_CHAINS` in the script, for setting up dynamic bones in Unity).

### 5.11 งูโคมไฟใต้ทะเล / The Abyssal Lantern Serpent (`art/models/serpent/`)

เจ้าของเลือกตัวที่ 4 จาก `concept-lineup-serpent-v2.png` แบบมีระยะการโต (`growth-lantern-v1.png`: เด็ก วัยรุ่น โต แก่) และวัยโตต้องแยกชิ้นอานกับเขา (`parts-lantern-adult-v1.png`) ตอนนี้ทำ 3D แล้วเฉพาะวัยโต
The owner picked #4 from `concept-lineup-serpent-v2.png`, with growth stages (`growth-lantern-v1.png`: baby, teen, adult, elder), and for the adult only the saddle and horns as separate parts (`parts-lantern-adult-v1.png`). Only the adult is in 3D so far.

1. ภาพเข้า Hyper3D ทำด้วย Codex: `render-body-lantern-v2.png` (ตัวเปล่า **ยืดยาวเกือบตรง** แบบปลาไหล) และ `render-saddle-lantern-v1.png` (อานอย่างเดียว) นำเข้าชื่อ `RodinSerpent` กับ `RodinSaddle`
   Hyper3D inputs drawn with Codex: `render-body-lantern-v2.png` (bare body, **stretched out almost straight** like an eel) and `render-saddle-lantern-v1.png` (saddle alone). Import them as `RodinSerpent` and `RodinSaddle`.
   - **บทเรียน:** รอบแรกใช้ตัวขดเป็นรูป S (`v1`) ท่าขดถูกฝังในโมเดล ได้ตัวสั้น เลื้อยได้แค่หาง ดูแข็ง งูต้องเริ่มจากตัวยืดยาว แล้วใช้กระดูกดัดเป็นท่าต่างๆ (Idle ยกคอเป็นตัว S ด้วยกระดูก)
     **Lesson:** the first try used a body coiled in an S (`v1`). The coil got baked into the mesh: a short body where only the tail could slither, and it looked stiff. A serpent must start stretched out; the bones then bend it into every pose (the Idle lifts the neck into the S).
2. หนวดโคม (เป็น "เขา" ของตัวนี้) ปั้นใน `art/tools/build_serpent.py` ใช้วัสดุแก้วโปร่งแสงกับเรืองแสงจริง
   The lantern antennae (this creature's "horns") are modelled in `art/tools/build_serpent.py`, with real see-through glass and glow materials.
3. รัน `art/tools/rig_serpent.py` / Run `art/tools/rig_serpent.py`:
   ```python
   p = "/path/to/GM-fron/art/tools/rig_serpent.py"
   exec(compile(open(p).read(), p, "exec"), {"__name__": "gm_serpent_rig", "__file__": p, "SOURCE": "RodinSerpent", "SADDLE": "RodinSaddle"})
   ```
   - หาแกนกลางลำตัว: จุดบนผิวยิงรังสีเข้าข้างใน จุดกึ่งกลางถึงผนังอีกด้านคือแกน ครีบบางๆ ถูกข้าม แล้วเรียงตามระยะบนผิวจากปลายหาง จุดที่ไกลที่สุดคือปลายจมูก
     Finds the body's axis: each skin point casts a ray inward and the midpoint to the far wall lies on the axis (thin fins are skipped), ordered by surface distance from the tail tip, so the farthest solid point is the snout.
   - Hyper3D หันตามรูป (ตัวนี้หันไปทาง +Y) สคริปต์จึงหมุนให้ปากชี้ -Y เหมือนโมเดลอื่น
     Hyper3D keeps the picture's facing (this one looked toward +Y), so the script turns it to face -Y like every other model.
   - กระดูกเป็นสาย ยึดที่จุดวางอาน (ช่วงลำตัวที่ราบที่สุดหลังคอ) คอวิ่งไปหัว หางวิ่งไปปลาย หนวดมีกระดูกของตัวเองสำหรับ physics
     One bone chain, rooted at the saddle spot (the most level stretch past the neck): the neck runs to the head, the tail to its tip; the antennae get their own bones for spring physics.
   - อาน: หาทิศรูวงแหวนจากความสมมาตรซ้ายขวา ยิงรังสีหารู แล้วร้อยเข้ากับลำตัวและปรับขนาดให้พอดี
     Saddle: finds which way its ring runs from its left-right symmetry, finds the hole by ray casting, then threads it onto the body and sizes it to fit.
   - ปรับขนาดให้ยาว 5 ม. หาหัวกับหางจากความหนา (ครีบที่บางกว่าราวหนึ่งในสามของลำตัวไม่นับ และตัดแนวตรงที่ย้อนกลับ ซึ่งเกิดจากครีบหนาๆ หลังหัว)
     Sizes it to 5 m long and tells head from tail by thickness (anything under about a third of the body's thickness counts as fin, and the line is cut where it doubles back, which a thick frill behind the head causes).
   - ท่า: คลื่นวิ่งทั้งตัวตั้งแต่คอถึงปลายหาง ทั้งซ้ายขวาและขึ้นลงเล็กน้อย หัวหันกลับให้มองตรงตลอด Idle ยกคอเป็นตัว S (ขึ้น 70° ลง 55° เกลี่ยทั่วคอ) Swim/Dash ตัวยืดเพรียว ลอยสูงจากพื้น 22 ซม. ความเร็วที่ตรงกับคลื่น: Swim 2.2 ม./วิ., Dash 3.4 ม./วิ. ส่งออกเป็น `generated/serpent.glb`
     Motion: one wave runs through the whole body, neck to tail tip, sideways plus a little up and down, and the head turns back against it to keep looking ahead. Idle lifts the neck into the S (70° up, 55° down, spread over the neck); Swim/Dash keep the body long and streamlined; it hovers 22 cm up. Matching speeds: Swim 2.2 m/s, Dash 3.4 m/s. Exports `generated/serpent.glb`.
4. ดูได้ที่ http://localhost:8765/horse/?model=serpent (physics หนวดอยู่ใน `MODELS.serpent.chains`)
   View it at http://localhost:8765/horse/?model=serpent (antenna physics in `MODELS.serpent.chains`).
5. **ระยะชีวิต:** ใส่ `"STAGE": "baby"` (หรือ `teen`, `elder`) ตอนรันสคริปต์ ค่าของแต่ละวัยอยู่ใน `STAGES` (ความยาว ขนาดหนวด ความสูงที่ลอย จำนวนสามเหลี่ยม มีอานไหม ชื่อไฟล์) ภาพเข้า Hyper3D คือ `render-body-baby-v1.png`, `render-body-teen-v1.png`, `render-body-elder-v1.png` (ภาพรวมขนาดจริง: `stages-stretched-v1.png`) ทุกวัยได้กระดูกชื่อเดียวกันและท่าเดียวกัน เกมจึงสลับโมเดลได้ตอนโต ทำครบทั้ง 4 วัยแล้ว: `serpent-baby.glb`, `serpent-teen.glb`, `serpent.glb`, `serpent-elder.glb` (ดูที่ `?model=serpentBaby`, `serpentTeen`, `serpent`, `serpentElder`) หัวกับหางแยกจากความกว้าง (หัวกว้าง ครีบหางแบน) ตัวแก่ใช้น้ำหนักตามแนวกลางลำตัว (`chain_skin`) เพราะหนวดใต้คางกับปะการังทำให้น้ำหนักอัตโนมัติของ Blender ล้มเหลว และได้โคมแก้วทะเลเก่า (`aged`) สคริปต์ลบชิ้นที่ลอยแยกจากตัว (`remove_floaters`, เช่นลูกกลมๆ ที่ Hyper3D เติมมาเหนือหลังตัวแก่) และปักหนวดบนจุดสูงสุดของกะโหลกโดยยิงรังสีจากข้างในหัว ไม่ให้ไปตั้งบนปะการัง
   **Life stages:** pass `"STAGE": "baby"` (or `teen`, `elder`) when running the script; each stage's settings are in `STAGES` (length, antenna size, hover height, triangle budget, saddle or not, output name). The Hyper3D inputs are `render-body-baby-v1.png`, `render-body-teen-v1.png`, `render-body-elder-v1.png` (true-size overview: `stages-stretched-v1.png`). Every stage gets the same bone names and clips, so the game can swap models as it grows. All four stages are done: `serpent-baby.glb`, `serpent-teen.glb`, `serpent.glb`, `serpent-elder.glb` (view at `?model=serpentBaby`, `serpentTeen`, `serpent`, `serpentElder`). Head and tail are told apart by width (a head is wide, a tail fin flat). The elder is weighted along its centre line (`chain_skin`) because its chin tendrils and coral make Blender's automatic weights fail, and it gets old sea-glass lanterns (`aged`). The script deletes pieces floating apart from the body (`remove_floaters`, e.g. a ball Hyper3D added above the elder's back), and plants the antennae on the crown of the skull by casting rays from inside the head, so they never sit on coral.

## 6. ตัวอย่างที่เจ้าของชอบ / References the owner likes

| ตัวอย่าง / Reference | เอามาใช้เรื่อง / Used for |
|---|---|
| [Lands of Koastalia](https://x.com/ValakhP/status/2107942463029882952) | ลุคหมู่บ้านมองจากมุมสูง / The high-angle village look |
| [tkduze: tool wheel](https://x.com/tkduze/status/2111466084243014005) | หญ้าหนาปลายสว่าง, ไถดินปลูกผักบน grid / Dense light-tipped grass, tilling and planting on a grid |
| [tkduze: storm](https://x.com/tkduze/status/2106126079790596560) | หญ้าเหมือนพรม ดอกไม้ส้ม เงาเมฆ พายุ / Carpet-like grass, orange flowers, cloud shadows, storm |
| [Lukas Schneider](https://x.com/zwitscherluki/status/2104934596873703480) | พุ่มใบนุ่มแบบภาพวาด พุ่มดอกสีชมพู / Soft painterly canopies, pink flowering bushes |
| [Unreal world (quoted post)](https://x.com/politicalmath/status/2112052470155477470) | ต้นไม้สูงแตกกิ่ง ใบไม้ร่วงหลายสี ต้นสน / Tall branching trees, multicoloured autumn leaves, pines |
| [Flavour Edge](https://www.instagram.com/reel/DegQXXYB1Bf/) | ชายหาด pixel art, เงาจริง, เงาสะท้อนบนน้ำ, กลางวัน-กลางคืน / Pixel-art beach, real shadows, water reflections, day-night |

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
5. ถางพื้นที่และแปลงแบบ server ตัดสิน: เก็บสถานะดินต่อช่อง `{ground, cleared_at, plot_id}` คำนวณความโตของหญ้าจากเวลา ข้อความ `ClearCell`, `DigStump`, `PlacePlot`, `LevelCell`, `LandUpdate`, `PlotState` / Server-authoritative clearing and plots: per-cell `{ground, cleared_at, plot_id}`, growth computed from time, and `ClearCell`, `DigStump`, `PlacePlot`, `LevelCell`, `LandUpdate`, `PlotState` messages.

**รอเจ้าของตัดสินใจ / Waiting on the owner:**
1. เอา concept A หรือ B / Concept A or B.
2. ระบบสร้างบ้าน: ถางพื้นที่และวางแปลงทำแล้วในทุ่งทดลอง ขั้นต่อไปคือสร้างบ้านบนแปลงที่ Ready และเรื่องสิทธิ์ (ผมเสนอให้วางแปลงได้เฉพาะโซนที่อยู่อาศัย) / Building: land clearing and plots are done in the meadow; next is building a house on a Ready plot, plus who may place plots where (proposed: housing zones only).
3. ตัวละครจริงจะใช้ตัวไหน (chibi ชั่วคราว หรือตัว Hero ในไฟล์ Blender ของเจ้าของ) / Which character model to use (the temporary chibi, or the Hero in the owner's Blender file).

## 8. เรื่องที่อาจเจอ / Gotchas

- ระบบพิกัด: ช่อง (x, y) = Blender (x, y) = three.js (x, 0, -y) ตอนเอาโมเดลเข้า Unity ต้องเช็คทิศแกนอีกที เพราะ glTF กับ Unity ใช้แกนต่างกัน
  Coordinates: cell (x, y) = Blender (x, y) = three.js (x, 0, -y). When the model goes into Unity, double-check the axes, since glTF and Unity use different conventions.
- material ที่เป็น procedural ใน Blender (หญ้า หินปูพื้น) export ออกไปไม่ได้ ตัวดูบนเว็บจึงสร้าง shader ใหม่เองตามชื่อ material ถ้าจะเอาเข้า Unity ต้อง bake เป็น texture หรือเขียน shader ใหม่
  Procedural Blender materials (grass, paving) don't export, so the web viewer rebuilds them as shaders by material name. For Unity, bake them to textures or write new shaders.
- `art/viewer/town.glb` ถูก ignore ใน git เพราะ generate ใหม่ได้ ตัวดูใช้ `town-glb.txt`
  `art/viewer/town.glb` is git-ignored because it's regenerated; the viewer uses `town-glb.txt`.
- สวิตช์ Hyper3D (และตัวเลือกอื่นของ Blender MCP) เก็บแยกต่อ scene ถ้าสคริปต์สร้าง scene ใหม่แล้วค้างไว้ที่ scene นั้น Hyper3D จะดูเหมือนปิดเอง ให้กลับไป scene เดิม (`rig_serpent.py` ทำให้แล้ว)
  The Hyper3D switch (and the Blender MCP's other options) is stored per scene. If a script builds a new scene and leaves it showing, Hyper3D looks switched off; go back to the original scene (`rig_serpent.py` now does).
- ถ้า Blender กระตุก ให้ดูว่า viewport ไม่ได้อยู่ในโหมด Rendered
  If Blender lags, make sure the viewport isn't in Rendered mode.
- Spring bone ใน three.js: AnimationMixer เขียนค่ากระดูกเฉพาะตอนค่าใน animation เปลี่ยน กระดูกที่ท่าค้างนิ่งจะไม่ถูกรีเซ็ต แรงงอจาก physics เลยสะสมทุกเฟรมจนหางพับและขาด ต้องเก็บท่าจาก animation ไว้แล้วคืนค่าก่อน `mixer.update` ทุกเฟรม (ดู `restoreTail`)
  Spring bones in three.js: the AnimationMixer only writes a bone when its animated value changes, so bones a clip holds still never get reset and the physics bend piles up every frame until the tail folds and tears. Save each bone's animated pose and restore it before every `mixer.update` (see `restoreTail`).
- three.js ตัดจุดออกจากชื่อ node ตอนโหลด glTF (`featherArm.L` กลายเป็น `featherArmL`) ใช้ชื่อแบบไม่มีจุดตอนเรียก `getObjectByName`
  three.js strips dots from glTF node names on load (`featherArm.L` becomes `featherArmL`), so use the dotless name with `getObjectByName`.
