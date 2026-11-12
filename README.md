# People Counter

Multi camera people counting system for CCTV / IP cameras.

* **Desktop app (PyQt6)** - live view, camera management, a graphical line and
  area editor, reports, users and settings.
* **Engine** - capture, YOLOv8n person detection, ByteTrack tracking and the
  counting logic. Runs headless, never blocks the GUI.
* **REST / WebSocket API (FastAPI)** - the same engine over HTTP, either
  embedded in the desktop app or as a standalone service.

---

## Table of contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Quick start](#quick-start)
5. [Configuration](#configuration)
6. [Adding a camera](#adding-a-camera)
7. [Drawing counting lines and areas](#drawing-counting-lines-and-areas)
8. [How a crossing is counted](#how-a-crossing-is-counted)
9. [Simulation mode](#simulation-mode)
10. [Roles and users](#roles-and-users)
11. [Reports and exports](#reports-and-exports)
12. [The HTTP API](#the-http-api)
13. [Building a Windows executable](#building-a-windows-executable)
14. [Running the tests](#running-the-tests)
15. [Project layout](#project-layout)
16. [Troubleshooting](#troubleshooting)

---

## Features

* Add cameras either by **IP + user + password + port + RTSP path** or by
  pasting a **full RTSP url**; camera passwords are encrypted in the database
  and never leave the API in clear text.
* **Test connection** button that grabs a single frame and shows it in the
  dialog.
* Automatic **reconnect with exponential backoff** and a coloured status
  indicator (online / offline / reconnecting) per camera.
* Draw **counting lines** (A to B, B to A or both directions) and **counting
  areas** (enter, exit, live occupancy) directly on a camera snapshot.
* Live grid of camera tiles with **per camera counters** and a **global
  summary bar** across all cameras.
* Only **humans** are counted - every other YOLO class is discarded.
* Reports with filters, aggregation per minute / hour / day / week / month,
  charts and **CSV / Excel / PDF export**.
* Three roles (admin, operator, viewer) with an **audit log** of all important
  actions.
* **API**: JWT plus API keys, MJPEG video streams, WebSocket count and
  detection feeds, optional webhooks.
* Optional **CUDA** acceleration with automatic CPU fallback.

---

## Architecture

`@
            +---------------------------+
            |        Desktop GUI        |
            |  PyQt6, talks to the      |
            |  engine through Qt signals |
            +-------------+-------------+
                          |
            +-------------v-------------+
            |          Engine           |   no GUI imports anywhere
            |  camera worker threads    |
            |  -> shared YOLO model      |
            |  -> ByteTrack per camera   |
            |  -> counting engine        |
            |  -> buffered DB writer     |
            +------+-------------+------+
                   |             |
        +----------v--+   +------v-------------------+
        | FastAPI API |   |      SQLite / Postgres   |
        | + WebSocket |   +--------------------------+
        +-------------+   (SQLAlchemy + Alembic)
`@

Three layers, exactly as required:

1. **`app/engine`** - camera workers, detector, tracker, counter, event queue.
   Contains no GUI code and runs headless.
2. **`app/gui`** - the PyQt6 desktop application. It talks to the engine
   in-process through Qt signals, so the GUI never blocks.
3. **`app/api` + `app/server.py`** - the same engine over HTTP. The server
   can run inside the desktop app (toggle in *Settings*) or standalone with
   `python -m app.server`.

Key design points:

* **One YOLO model instance** for all cameras. Frames from different cameras
  are collected during a short window and handed to the model as one batch.
* **One annotated frame per camera** is produced and shared by the GUI tiles,
  the MJPEG stream and the WebSocket output - detection is never re-run per
  viewer.
* **DB writes never block inference**: count events go into a queue that a
  dedicated writer thread flushes in batches.

---

## Installation

Requires **Python 3.11+** (developed and tested on 3.12).

`@bash
git clone <your-repo> people-counter
cd people-counter

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
`@

For a GPU install the matching CUDA build of PyTorch first:

`@bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
`@

The detector uses CUDA automatically when it is available.

---

## Quick start

`@bash
# 1) create the sample video for testing (optional but recommended)
python -m app.tools.sample_data

# 2) start the desktop application
python -m app.main

# 3) or run the API only, without a GUI
python -m app.server --host 0.0.0.0 --port 8000
`

### Web UI auto-start

When you start the API server (`python -m app.server`), the Persian web UI
starts and opens in your browser automatically:

* If `web-ui/dist` exists (run `npm run build` inside `web-ui` once), the
  production build is served by the API itself at `http://<host>:<port>/` -
  no Node.js needed at run time.
* Otherwise the Vite dev server (`npm run dev`) is spawned in `web-ui` and the
  browser opens on `http://localhost:3100`. Dependencies are installed
  automatically on the first run.
* Disable with `--no-web` or `PCC_WEB_UI=off` in `.env`.@

On the very first start a default administrator is created:

| user | password |
| ---- | -------- |
| `admin` | `admin123` |

The password must be changed at the first login. Change it immediately in a
real installation, and set `PCC_SECRET_KEY` to a long random string.

---

## Configuration

Everything is configured through environment variables (or a `.env` file in the
project root). Copy the template and edit it:

`@bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux / macOS
`@

All variables use the `PCC_` prefix. The most important ones:

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `PCC_DATABASE_URL` | `sqlite:///./data/people_counter.db` | SQLite or PostgreSQL |
| `PCC_SECRET_KEY` | `dev-secret-change-me` | JWT signing key and credential encryption key |
| `PCC_MODEL_NAME` | `yolov8n.pt` | Weights file, downloaded into `data/models` on first use |
| `PCC_CONFIDENCE` | `0.4` | Detection confidence |
| `PCC_IOU` | `0.7` | NMS IoU threshold |
| `PCC_IMGSZ` | `640` | Inference size |
| `PCC_DEVICE` | `auto` | `auto`, `cpu` or `0` for the first CUDA device |
| `PCC_BATCH_SIZE` | `4` | Frames inferred together across cameras |
| `PCC_TRACK_POINT` | `bottom` | `bottom` (feet) or `center` |
| `PCC_COUNTING_COOLDOWN_S` | `1.5` | Anti jitter cooldown per track and zone |
| `PCC_API_ENABLED` | `false` | Start the embedded API with the GUI |
| `PCC_API_HOST` / `PCC_API_PORT` | `127.0.0.1` / `8000` | API bind address |
| `PCC_WEBHOOK_URLS` | - | Comma separated list of webhook targets |

### Switching to PostgreSQL

One value, no code change:

`@env
PCC_DATABASE_URL=postgresql+psycopg://people:secret@localhost:5432/people_counter
`@

Create the database, then apply the migrations:

`@bash
pip install "psycopg[binary]"
alembic upgrade head
`@

SQLite databases are created automatically on the next start.

---

## Adding a camera

Open the **Cameras** page and press *Add camera*. The dialog has three tabs.

**Tab 1 - Manual (IP / user / pass).** Fill in the IP address, the port
(default 554), the user name, the password and the RTSP path (for example
`/stream1`). The application builds the url itself:

`@
rtsp://user:pass@192.168.1.64:554/stream1
`@

Special characters in the user name or password are URL encoded
automatically, so `p@ss/word` is sent as `p%40ss%2Fword`.

**Tab 2 - Direct RTSP URL.** Paste the complete url, for example
`rtsp://admin:secret@192.168.1.64:554/Streaming/Channels/101`. The credentials
are extracted, encrypted and stored separately - the url is stored without
them.

**Tab 3 - Video file (simulation).** Pick any video file. This is the easiest
way to test the whole system without a real camera.

Press **Test connection** to open the stream and see a preview frame. The
dialog reports the resolution and the frame rate of the source.

The password is encrypted with a key derived from `PCC_SECRET_KEY`, is masked
in the interface and logs, and is never returned by the API.

---

## Drawing counting lines and areas

Open **Lines and areas**, select a camera and press *Open editor*.

* The editor shows a live snapshot of the camera.
* Pick the mode in the toolbar:
  * **Draw line** - click point A, then point B.
  * **Draw area** - click the points of the polygon, double click to close it.
  * **Select / move points** - drag the round handles to adjust the geometry.
* Choose the direction of the line: `A -> B`, `B -> A` or `Both directions`.
* The list on the right lets you rename, enable or disable and delete objects.
* Everything is stored in **normalised coordinates (0..1)**, so the same
  geometry works at any resolution.

Arrows drawn on the video show exactly which walking direction is counted as
**IN** (and as **OUT** for bidirectional lines).

### Areas

An area counts entries, exits and the **live occupancy** (how many people are
inside right now). Occupancy is shown per area in the counts and summed up in
the global summary.

---

## How a crossing is counted

The counting point of a person is the **bottom centre of the bounding box**
(the feet) by default; `PCC_TRACK_POINT=center` switches to the centre of the
box.

A crossing is detected when the **movement segment** of a track (previous
position to current position) intersects the line segment. The direction is
derived from the movement relative to the line:

* Movement **along** the line: the sign of the projection on `A -> B` decides.
  Walking towards B is `A -> B`, walking back is `B -> A`.
* Movement **across** the line (the normal case): the half plane the person
  moves into decides. Walking into the half plane on the left of `A -> B` is
  an `A -> B` crossing, the opposite half plane is `B -> A`.

Because people usually walk across a line, the counted direction is shown as an
arrow on the video.

Further rules:

* Every track id counts **once per crossing**.
* A **cooldown** (`PCC_COUNTING_COOLDOWN_S`, default 1.5 s) plus a minimum
  displacement prevents a person standing on the line from being counted
  repeatedly.
* The first observation of a track never counts - a crossing needs two
  positions.
* Only the **person class (0)** is counted; cars, bikes and animals are
  dropped before tracking.

Direction mapping per configured line direction:

| Line direction | `A -> B` crossing | `B -> A` crossing |
| -------------- | ----------------- | ----------------- |
| `A_TO_B` | counted as **IN** | ignored |
| `B_TO_A` | ignored | counted as **IN** |
| `BOTH` | counted as **IN** | counted as **OUT** |

---

## Simulation mode

Create the sample video (a person walks across the scene and back):

`@bash
python -m app.tools.sample_data
`@

This writes `data/sample/sample_walk.mp4`. Add a camera with the
*Video file* tab, point it at that file and draw a line in the middle of the
picture - the person is detected, tracked and counted in both directions.

Any other video file works as well.

---

## Roles and users

| Role | Permissions |
| ---- | ----------- |
| **admin** | everything, including user management, settings and resetting counters |
| **operator** | manage cameras and lines, view and export reports |
| **viewer** | read only: live view and reports |

* The login dialog appears when the application starts; users can log out and
  change their own password at any time.
* The first login with the default admin account forces a password change.
* Pages and buttons the role may not use are hidden or disabled.
* The **Users** page (admin only) manages accounts and shows the audit log of
  logins, camera and user changes and counter resets.

---

## Reports and exports

The **Reports** page filters by date range, cameras and direction, and
aggregates per minute, hour, day, week or month. It shows a time series, the
peak hours and a camera comparison, plus a summary table.

Exports are available as **CSV**, **Excel** (.xlsx) and **PDF**. The same
exports are available through the API (`/api/v1/reports/export`).

---

## The HTTP API

Start the server standalone:

`@bash
python -m app.server --host 0.0.0.0 --port 8000
`@

or from the desktop app: *Settings -> API server -> Start / restart API*.

Interactive documentation is available at `http://<host>:<port>/docs`.

### Authentication

`@bash
# login
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username":"admin","password":"admin123"}'

# use the token
curl http://127.0.0.1:8000/api/v1/cameras \\
  -H "Authorization: Bearer <ACCESS_TOKEN>"
`@

Machine to machine clients use an API key instead:

`@bash
curl -X POST http://127.0.0.1:8000/api/v1/users/api-keys \\
  -H "Authorization: Bearer <ACCESS_TOKEN>" \\
  -H "Content-Type: application/json" \\
  -d '{"name":"integration"}'

curl http://127.0.0.1:8000/api/v1/cameras -H "X-API-Key: pcc_..."
`@

### Endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/api/v1/auth/login` | login, returns access and refresh token |
| POST | `/api/v1/auth/refresh` | refresh the access token |
| GET | `/api/v1/auth/me` | current user |
| POST | `/api/v1/auth/change-password` | change own password |
| GET/POST/PATCH/DELETE | `/api/v1/users...` | user management (admin) |
| GET/POST/PATCH/DELETE | `/api/v1/cameras...` | camera management |
| POST | `/api/v1/cameras/{id}/test` | test the connection |
| GET | `/api/v1/cameras/{id}/status` | live status of one camera |
| GET | `/api/v1/cameras/{id}/snapshot` | single JPEG frame |
| GET | `/api/v1/cameras/{id}/stream` | MJPEG stream with annotations |
| GET | `/api/v1/cameras/{id}/stream/raw` | MJPEG stream without annotations |
| GET/POST/PATCH/DELETE | `/api/v1/cameras/{id}/lines...` | counting lines |
| GET/POST/PATCH/DELETE | `/api/v1/cameras/{id}/areas...` | counting areas |
| GET | `/api/v1/counts` | global live counters |
| GET | `/api/v1/counts/camera/{id}` | counters of one camera |
| GET | `/api/v1/counts/events` | recent counting events |
| GET | `/api/v1/reports/summary` | aggregated report |
| GET | `/api/v1/reports/export` | CSV / Excel / PDF download |
| WS | `/api/v1/ws/counts` | live count events (JSON) |
| WS | `/api/v1/ws/cameras/{id}/detections` | live boxes and track ids |

### Examples

`@bash
# add a camera with manual fields
curl -X POST http://127.0.0.1:8000/api/v1/cameras \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"name":"Front door","mode":"manual","host":"192.168.1.64","port":554,
       "username":"admin","password":"secret","rtsp_path":"/stream1"}'

# add a camera with a direct url
curl -X POST http://127.0.0.1:8000/api/v1/cameras \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"name":"Loading bay","mode":"url",
       "url":"rtsp://admin:secret@192.168.1.65:554/stream2"}'

# draw a counting line
curl -X POST http://127.0.0.1:8000/api/v1/cameras/1/lines \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"name":"Main door","x1":0.2,"y1":0.5,"x2":0.8,"y2":0.5,"direction":"A_TO_B"}'

# live video in a browser: http://127.0.0.1:8000/api/v1/cameras/1/stream

# live counts
curl http://127.0.0.1:8000/api/v1/counts -H "Authorization: Bearer $TOKEN"

# export a report
curl "http://127.0.0.1:8000/api/v1/reports/export?format=pdf" \\
  -H "Authorization: Bearer $TOKEN" -o report.pdf
`@

### WebSocket example

`@javascript
const socket = new WebSocket("ws://127.0.0.1:8000/api/v1/ws/counts?token=<ACCESS_TOKEN>");
socket.onmessage = (event) => console.log(JSON.parse(event.data));
`@

### Webhooks

Set `PCC_WEBHOOK_URLS` to one or more urls. Every counting event is posted as
`{"event": "count", "data": {...}}`.

---

## Building a Windows executable

`@bash
pip install pyinstaller
pyinstaller build_exe.spec
`@

The result is `dist/PeopleCounter/PeopleCounter.exe`. Build it on Windows -
PyInstaller does not cross compile. The model weights are downloaded on the
first start of the application, so the build stays small.

Linux / macOS:

`@bash
pip install pyinstaller
pyinstaller --noconfirm build_exe.spec
./dist/PeopleCounter/PeopleCounter
`@

---

## Running the tests

`@bash
pip install pytest
python -m pytest
`@

The suite covers

* the counting logic - crossings in each direction, jitter and cooldown,
  polygon enter / exit, occupancy and the totals,
* the pipeline - detection, tracking, counting and persistence into the
  database, including the rule that only humans are counted,
* the API - authentication, roles and permissions, camera / line / area CRUD,
  counts, reports and the exports.

An additional integration test runs the **real YOLO model** against the
generated sample video. Generate the sample data once and it is picked up
automatically:

`@bash
python -m app.tools.sample_data
python -m pytest
`@

---

## Project layout

`@
app/
  engine/        camera_worker, detector, tracker, counter, camera_manager, event_queue
  db/            models, session, migrations (Alembic)
  services/      auth, audit, reports, export, webhooks, cameras
  api/v1/        routers and pydantic schemas
  gui/           main_window, login_dialog, live_view, camera_tile, camera_dialog,
                 zone_editor, reports_page, users_page, settings_page, resources
  tools/         sample_data (creates the simulation video)
  server.py      headless API entry point
  main.py        GUI entry point
tests/
.env.example
requirements.txt
build_exe.spec      (PyInstaller)
alembic.ini
README.md
`@

---

## Troubleshooting

**The video stays black / no detections**
Check *Cameras -> Test connection*. If the connection works but nothing is
detected, raise `PCC_CONFIDENCE` step by step (0.25, 0.15) and check the
*overlay* switch of the tile. The log file in `logs/people_counter.log` shows
whether the model could be loaded.

**The camera shows "reconnecting"**
The stream is not reachable. The worker retries automatically with an
exponential backoff (1 s ... 30 s). Common causes: wrong credentials, wrong
RTSP path, or the port being blocked.

**The app is slow with many cameras**
Lower `PCC_IMGSZ` to 480, reduce the per camera frame rate in the camera
dialog, or use a GPU (`PCC_DEVICE=0`).

**Counts seem off**
Check that the counting point matches your scene (`bottom` = feet). Check the
cooldown: a person standing on the line is only counted once per cooldown
window.

**Port 8000 is already in use**
Change `PCC_API_PORT` or the port in *Settings -> API server*.

**Everything is slow after the first start**
The model weights (`yolov8n.pt`, about 6 MB) are downloaded into
`data/models` on the first run.
