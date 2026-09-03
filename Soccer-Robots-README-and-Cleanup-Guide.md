# Soccer Robots Raspberry Pi Runtime

This repository contains the Raspberry Pi side of the Soccer Robots project.

The Raspberry Pi acts as the bridge between:

- the Soccer Robots website
- the game manager
- player controller input
- ESP32-controlled robots
- the arena camera
- Janus WebRTC video streaming

The normal Raspberry Pi runtime is started with a single command:

```bash
./start_soccer_robot.sh
```

and stopped with:

```bash
./stop_soccer_robot.sh
```

---

# System Architecture

The Raspberry Pi currently runs four major subsystems:

```text
                        Soccer Robots Client
                         /              \
                        /                \
                       v                  v
              Game / Controller       WebRTC Video
                       |                  ^
                       |                  |
                  WebSockets             |
                 1234 / 1235             |
                       |                  |
                       v                  |
               Raspberry Pi              |
                       |                  |
        +--------------+-----------+      |
        |              |           |      |
        v              v           v      |
   GmServerPi     ControllerPi    Janus ---+
        \              /
         \            /
          v          v
            EspManager
                |
                |
          TCP to ESP32
                |
                v
             Robots
```

The camera path is:

```text
IMX219 Camera
      |
      v
rpicam-vid
      |
      | H.264 inside MPEG-TS
      v
GStreamer
      |
      | RTP / H.264
      | UDP 127.0.0.1:5006
      v
Janus Streaming Plugin
      |
      | WebRTC
      v
Soccer Robots Client
```

Janus receives one camera stream and can distribute that same stream to multiple WebRTC clients.

This avoids opening the Raspberry Pi camera separately for every player.

---

# Tested Platform

The current runtime has been developed and tested with:

```text
Raspberry Pi:      Raspberry Pi 4
Operating System:  Raspberry Pi OS / Debian 13 (trixie)
Architecture:      aarch64
Camera:            IMX219
Camera interface:  libcamera / rpicam
```

The current Soccer Robots hotspot address is:

```text
10.42.0.1
```

This address is used by the Game Manager, Controller, and Janus development configuration.

---

# Runtime Components

## EspManager.py

`EspManager.py` is the central robot communication process.

It receives:

- game state from `GmServerPi.py`
- movement commands from `ControllerPi.py`

It then routes those commands to the correct ESP32.

For every active player, EspManager creates a child process.

Conceptually:

```text
EspManager
    |
    +-- child 0 --> ESP32 / Robot 0
    |
    +-- child 1 --> ESP32 / Robot 1
    |
    +-- child 2 --> ESP32 / Robot 2
    |
    ...
```

The parent communicates with the children using Unix pipes.

The child processes communicate with ESP32 boards through `ESPClient.py`.

### Mock ESP mode

`EspManager.py` contains:

```python
MOCK_ESP = True
```

When enabled, physical ESP32 connections are skipped and movement/reset messages are printed instead.

This is useful for Raspberry Pi and website testing without robot hardware.

For real robot testing this must eventually be:

```python
MOCK_ESP = False
```

Make sure the ESP addresses are correct before disabling mock mode.

---

## ESPClient.py

`ESPClient.py` wraps the TCP connection between a Raspberry Pi child process and an ESP32.

It handles operations such as:

```text
connect
send
receive
connection failure handling
```

ESP32 communication currently uses TCP port:

```text
30000
```

---

## GmServerPi.py

`GmServerPi.py` connects the Raspberry Pi to the website Game Manager.

It listens at:

```text
ws://10.42.0.1:1234
```

It handles messages such as:

```text
CHECK_READY
game start
timer updates
score updates
game end
```

When checking robot readiness:

```text
Website
    |
    v
GmServerPi
    |
    | "ready?"
    v
EspManager
    |
    v
ESP children
    |
    v
ESP32
```

The final ready result is then sent back to the website.

The player count is sent from GmServerPi to EspManager as a single byte when EspManager is initialized.

---

## ControllerPi.py

`ControllerPi.py` receives movement commands from the website Controller server.

It listens at:

```text
ws://10.42.0.1:1235
```

Controller messages sent to EspManager are fixed-size messages similar to:

```text
0|1000
1|0100
```

The first value identifies the player.

The final four characters represent movement input.

Example:

```text
1000 -> up
0100 -> left
0010 -> down
0001 -> right
0000 -> stop
```

EspManager routes the movement data to the correct child process.

---

# Raspberry Pi IPC

GmServerPi and ControllerPi communicate with EspManager through Unix sockets.

```text
/tmp/gmESPSocket
/tmp/controlESPSocket
```

These sockets use:

```text
AF_UNIX
SOCK_STREAM
```

The startup and shutdown scripts remove stale copies of these sockets.

---

# Shared Game Timer

EspManager and GmServerPi share game state through:

```text
/tmp/shared_timer
```

The timer is implemented using memory mapping.

When the game ends, the shared value reaches zero.

EspManager detects this and sends a reset command to each robot child process.

---

# Network Ports

| Port | Protocol | Purpose |
|---|---|---|
| 1234 | WebSocket/TCP | Website Game Manager → GmServerPi |
| 1235 | WebSocket/TCP | Website Controller → ControllerPi |
| 8088 | HTTP | Janus REST API |
| 5006 | RTP/UDP | GStreamer camera stream → Janus |
| 30000 | TCP | Raspberry Pi → ESP32 |

---

# First-Time Raspberry Pi Setup

## Clone the repository

```bash
git clone https://github.com/Soccer-Robots/Raspberry-Pi.git
cd Raspberry-Pi
```

Checkout the desired development branch if needed.

For example:

```bash
git checkout Damian
```

---

# Python Environment

The Raspberry Pi services run from the repository virtual environment:

```text
.venv/
```

Create one if needed:

```bash
python3 -m venv --system-site-packages .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

The startup script does not depend on the shell's currently activated environment.

It explicitly uses:

```text
.venv/bin/python
```

This prevents the Python services from accidentally starting with the wrong Python interpreter.

---

# Camera Setup

The current camera is an IMX219.

Verify camera detection with:

```bash
rpicam-hello --list-cameras
```

A working system should show an IMX219 camera.

Example supported modes include:

```text
640x480
1640x1232
1920x1080
3280x2464
```

For the Soccer Robots WebRTC stream we currently use:

```text
640x480
30 FPS
```

If the camera cannot be detected, inspect:

```bash
/boot/firmware/config.txt
```

Some installations may require the IMX219 overlay.

For example:

```text
camera_auto_detect=0
dtoverlay=imx219
```

Reboot after changing camera configuration:

```bash
sudo reboot
```

---

# Wi-Fi / Soccer Robots Hotspot

The Raspberry Pi currently acts as the Soccer Robots network host.

The expected address is:

```text
10.42.0.1
```

A NetworkManager hotspot can be created with:

```bash
sudo nmcli device wifi hotspot \
    ssid [hotspot-name] \
    password [hotspot-password] \
    ifname wlan1
```

The exact interface name may differ depending on the installed Wi-Fi adapter.

Useful commands:

```bash
ip addr
```

```bash
nmcli device
```

```bash
lsusb
```

```bash
lsusb -t
```

---

# Janus WebRTC Streaming

Soccer Robots uses Janus Gateway for the low-latency player camera feed.

Janus itself is intentionally not committed to this repository.

The installed production runtime lives at:

```text
~/soccerrobots-runtime/janus
```

Janus source used during installation is stored outside the repository at:

```text
~/soccerrobots-build/janus-gateway
```

The repository contains the installer needed to recreate the runtime.

---

# Install the Streaming Runtime

Run:

```bash
./scripts/install_streaming_runtime.sh
```

The installer:

1. installs required system dependencies
2. downloads Janus source
3. checks out the known-good Janus revision
4. builds Janus
5. installs it into `~/soccerrobots-runtime/janus`
6. installs the Soccer Robots Janus configuration
7. verifies the required GStreamer elements

The known-good Janus revision is intentionally pinned so another Raspberry Pi can reproduce the tested environment.

The Janus build used for Soccer Robots enables the REST HTTP transport and Streaming plugin.

Features not currently required by Soccer Robots, such as Janus WebSockets and data channels, are disabled in the lightweight build.

---

# Janus Configuration

Project-owned Janus configuration is stored in:

```text
config/janus/
```

Important files:

```text
config/janus/janus.plugin.streaming.jcfg
config/janus/janus.transport.http.jcfg
```

The camera streaming mountpoint is:

```text
ID:             43
Description:    Soccer Robots Camera
Video:          enabled
Audio:          disabled
Codec:          H.264
RTP port:       5006
Payload type:   96
```

The H.264 configuration uses:

```text
packetization-mode=1
profile-level-id=42e01f
```

Janus HTTP API:

```text
http://10.42.0.1:8088/janus
```

---

# Camera Streaming Pipeline

The working camera pipeline is managed by:

```text
scripts/start_streaming.sh
```

Conceptually:

```text
rpicam-vid
    |
    | MPEG-TS
    v
GStreamer fdsrc
    |
    v
tsdemux
    |
    v
h264parse
    |
    v
rtph264pay
    |
    | UDP :5006
    v
Janus
```

Current camera settings:

```text
Resolution:       640x480
Frame rate:       30 FPS
Codec:            H.264
Bitrate:          1 Mbps
Keyframe period:  10 frames
Container:        MPEG-TS
```

---

# Why MPEG-TS Is Used

An earlier streaming proof of concept used:

```text
rpicam-vid
      |
raw H.264 stdout
      |
GStreamer
```

The video worked, but playback was extremely jumpy.

The camera itself was verified to have very low latency using the older Picamera2/MJPEG server.

The problem was therefore isolated to the H.264/GStreamer path.

The improved pipeline became:

```text
rpicam-vid
      |
H.264 inside MPEG-TS
      |
tsdemux
      |
RTP
      |
Janus
```

Using MPEG-TS preserved usable stream timing/pacing through the pipe.

The resulting Janus stream became dramatically smoother and faster.

For that reason, do not casually replace the MPEG-TS handoff with a raw H.264 stdout pipe.

---

# Camera Process Management

The camera pipeline contains multiple processes:

```text
bash
rpicam-vid
gst-launch-1.0
```

`scripts/start_streaming.sh` starts the pipeline inside its own process group using `setsid`.

That allows the shutdown script to terminate the complete camera pipeline without globally killing unrelated GStreamer or camera processes.

Runtime state is stored in:

```text
/tmp/soccerrobots-streaming/
```

including the Janus PID and camera process group ID.

---

# Starting Streaming Independently

Streaming can be started without the robot services:

```bash
./scripts/start_streaming.sh
```

Verify:

```bash
pgrep -af "janus|rpicam-vid|gst-launch"
```

Verify Janus:

```bash
ss -ltnp | grep 8088
```

Verify Janus RTP input:

```bash
ss -lunp | grep 5006
```

Stop streaming:

```bash
./scripts/stop_streaming.sh
```

---

# Starting the Entire Soccer Robots Runtime

Normally, do not start individual processes manually.

Use:

```bash
./start_soccer_robot.sh
```

The startup order is:

```text
1. EspManager.py
2. GmServerPi.py
3. ControllerPi.py
4. Janus
5. Camera/GStreamer pipeline
```

The order of the first three services matters because they establish Unix socket connections with EspManager.

The startup script:

- verifies `.venv/bin/python`
- prevents duplicate services
- removes stale Unix sockets
- clears runtime logs
- starts EspManager
- verifies EspManager survived startup
- starts GmServerPi
- verifies GmServerPi
- starts ControllerPi
- verifies ControllerPi
- starts Janus
- starts the camera pipeline
- rolls back already-started services if streaming fails

---

# Stopping Soccer Robots

Stop the complete runtime with:

```bash
./stop_soccer_robot.sh
```

This stops:

```text
camera pipeline
Janus
ControllerPi
GmServerPi
EspManager
```

and removes runtime socket/shared-memory state.

After stopping, verify:

```bash
pgrep -af "EspManager|GmServerPi|ControllerPi|janus|rpicam-vid|gst-launch"
```

There should be no Soccer Robots runtime processes remaining.

---

# Logs

Main service logs:

```text
logs/esp.txt
logs/GMServer.txt
logs/Controller.txt
logs/janus.txt
logs/camera_stream.txt
```

View the ESP Manager log:

```bash
tail -f logs/esp.txt
```

View Game Manager:

```bash
tail -f logs/GMServer.txt
```

View Controller:

```bash
tail -f logs/Controller.txt
```

View Janus:

```bash
tail -f logs/janus.txt
```

View camera/GStreamer:

```bash
tail -f logs/camera_stream.txt
```

Runtime logs should not be committed to Git.

---

# Runtime Verification

Check all processes:

```bash
pgrep -af \
"EspManager|GmServerPi|ControllerPi|janus|rpicam-vid|gst-launch"
```

A normal running system should contain:

```text
EspManager.py
GmServerPi.py
ControllerPi.py
janus
rpicam-vid
gst-launch-1.0
```

Check TCP services:

```bash
ss -ltnp | grep -E '1234|1235|8088'
```

Expected:

```text
1234
1235
8088
```

Check RTP:

```bash
ss -lunp | grep 5006
```

---

# Soccer Robots Client Integration

The Client repository displays the Janus stream through:

```text
components/Gameplay/VideoStream.vue
```

The Client receives Janus configuration through Nuxt public runtime configuration.

Development environment:

```env
NUXT_PUBLIC_JANUS_URL=http://10.42.0.1:8088/janus
NUXT_PUBLIC_JANUS_STREAM_ID=43
```

The intended current behavior is:

```text
User not in game
      |
      v
Spectator stream / Twitch

User enters game
      |
      v
isInGame = true
      |
      v
Janus WebRTC
```

When the user leaves or the game ends:

```text
isInGame = false
```

and the Janus WebRTC session is cleaned up.

The Client also contains reconnect logic so a temporary Janus interruption does not necessarily require refreshing the page.

---

# Local WebRTC Networking

The current Janus configuration is primarily a local-network development configuration.

The Client connects directly to:

```text
10.42.0.1
```

and currently does not depend on an external STUN server for the local Soccer Robots network.

For a future internet-facing deployment, NAT traversal, firewall configuration, HTTPS, secure Janus access, and potentially STUN/TURN infrastructure will need to be considered.

A website loaded over HTTPS should not be expected to freely access an insecure HTTP Janus endpoint because browsers may block mixed content.

---

# Camera Ownership

The IMX219 can normally only be acquired by one camera application at a time.

Do not simultaneously run:

```text
cleanCode.py
```

and:

```text
rpicam-vid
```

Both attempt to own the camera.

Typical error:

```text
Pipeline handler in use by another process
Failed to acquire camera: Device or resource busy
```

Check camera owners with:

```bash
pgrep -af "rpicam-vid|cleanCode.py"
```

---

# Legacy MJPEG Camera Server

`cleanCode.py` is the older Picamera2/MJPEG streaming implementation.

It was useful during development because it provided a nearly instantaneous camera stream and helped isolate latency problems in the first Janus proof of concept.

It is no longer part of the normal Soccer Robots startup path.

The current production player stream uses:

```text
rpicam-vid
    -> MPEG-TS
    -> GStreamer
    -> RTP
    -> Janus
    -> WebRTC
```

If an MJPEG spectator stream is added in the future, the preferred design is to avoid acquiring the camera a second time.

Instead, one camera capture pipeline should feed multiple output paths.

---

# Troubleshooting

## ECONNREFUSED 10.42.0.1:1234

Check GmServerPi:

```bash
pgrep -af GmServerPi
```

Check the port:

```bash
ss -ltnp | grep 1234
```

Check:

```bash
cat logs/GMServer.txt
```

---

## Controller port 1235 unavailable

Check:

```bash
pgrep -af ControllerPi
```

```bash
ss -ltnp | grep 1235
```

```bash
cat logs/Controller.txt
```

---

## Protocol wrong type for socket

EspManager, GmServerPi, and ControllerPi must agree on the Unix socket type.

The current implementation uses:

```python
socket.AF_UNIX
socket.SOCK_STREAM
```

Do not mix `SOCK_STREAM` with `SOCK_SEQPACKET`.

---

## Incorrect player count such as 114

The Game Manager/ESP protocol sends the player count as one binary byte.

The string:

```text
ready?
```

must not be interpreted as the player count.

ASCII:

```text
'r' = 114
```

which was the cause of an earlier bug.

---

## Camera busy

Run:

```bash
pgrep -af "rpicam-vid|cleanCode.py"
```

Stop the conflicting camera process.

---

## Janus is not running

Check:

```bash
pgrep -af janus
```

Check:

```bash
ss -ltnp | grep 8088
```

Check:

```bash
tail -n 100 logs/janus.txt
```

Verify installation:

```bash
~/soccerrobots-runtime/janus/bin/janus --version
```

---

## Camera pipeline fails

Check:

```bash
tail -n 100 logs/camera_stream.txt
```

Verify required GStreamer elements:

```bash
gst-inspect-1.0 tsdemux
gst-inspect-1.0 h264parse
gst-inspect-1.0 rtph264pay
```

---

## Janus backend works but Client video does not

First verify:

```text
Camera
 -> GStreamer
 -> RTP
 -> Janus
```

If a known-good Janus viewer can display the camera, then the problem is likely on the Client side rather than Raspberry Pi streaming.

Check the browser developer console for:

```text
Janus initialization errors
ICE failures
WebRTC negotiation failures
mixed-content errors
```

---

# Known Limitations

## Player count initialization

EspManager currently determines the number of players when it first initializes.

Changing from, for example:

```text
2 players
```

to:

```text
4 players
```

without restarting EspManager is not currently supported.

Restart the Soccer Robots runtime if the player-count topology changes.

---

## Camera can only have one owner

The current Janus pipeline and legacy Picamera2/MJPEG implementation cannot independently acquire the IMX219 at the same time.

---

## Local Janus address

The current Janus URL:

```text
http://10.42.0.1:8088/janus
```

is designed around the Soccer Robots local network.

A public/internet deployment will require additional networking and security work.

---

## Physical ESP configuration

Mock mode is still useful during development.

Real hardware operation requires:

```python
MOCK_ESP = False
```

and valid ESP32 addresses.

---

# Important Repository Files

```text
start_soccer_robot.sh
    Starts the complete Soccer Robots Raspberry Pi runtime.

stop_soccer_robot.sh
    Stops the complete runtime.

scripts/EspManager.py
    Coordinates robots and creates per-player ESP child processes.

scripts/ESPClient.py
    TCP helper for communication with ESP32 boards.

scripts/GmServerPi.py
    Website Game Manager WebSocket server.

scripts/ControllerPi.py
    Website Controller WebSocket server.

scripts/start_streaming.sh
    Starts Janus and the camera/GStreamer pipeline.

scripts/stop_streaming.sh
    Stops Janus and the camera process group.

scripts/install_streaming_runtime.sh
    Reproduces the Janus/GStreamer runtime on another Raspberry Pi.

config/janus/
    Soccer Robots-owned Janus configuration.

oled_info_display.py
oled_info_display.service
    Raspberry Pi IP/status display support.
```

---

# Development Notes

The current streaming architecture was selected after testing several approaches.

The important progression was:

```text
Picamera2 / MJPEG
    -> very responsive
    -> not suitable as the final player WebRTC architecture

Janus + VP8 test source
    -> smooth
    -> proved Janus could fan one stream out to multiple browsers

IMX219 -> raw H.264 -> GStreamer -> Janus
    -> worked
    -> extremely jumpy

IMX219 -> H.264/MPEG-TS -> GStreamer -> Janus
    -> smooth
    -> low latency
    -> selected architecture
```

The final proof of concept was tested simultaneously in multiple browsers before being integrated into the Soccer Robots runtime and Client.

---

# Useful Development Commands

Start:

```bash
./start_soccer_robot.sh
```

Stop:

```bash
./stop_soccer_robot.sh
```

Check processes:

```bash
pgrep -af \
"EspManager|GmServerPi|ControllerPi|janus|rpicam-vid|gst-launch"
```

Check ports:

```bash
ss -ltnp | grep -E '1234|1235|8088'
```

Check RTP:

```bash
ss -lunp | grep 5006
```

Check camera:

```bash
rpicam-hello --list-cameras
```

Check throttling:

```bash
vcgencmd get_throttled
```

A healthy Raspberry Pi normally reports:

```text
throttled=0x0
```

Check temperature:

```bash
vcgencmd measure_temp
```

Check system load:

```bash
top
```

---

# Full Cold-Start Test

Stop everything:

```bash
./stop_soccer_robot.sh
```

Verify no runtime processes remain:

```bash
pgrep -af \
"EspManager|GmServerPi|ControllerPi|janus|rpicam-vid|gst-launch"
```

Start everything:

```bash
./start_soccer_robot.sh
```

Verify:

```bash
pgrep -af \
"EspManager|GmServerPi|ControllerPi|janus|rpicam-vid|gst-launch"
```

Then verify:

```bash
ss -ltnp | grep -E '1234|1235|8088'
```

Finally test the actual Soccer Robots Client and confirm:

```text
spectator
    ->
player joins game
    ->
Janus stream appears
    ->
game ends
    ->
Janus session closes
```

This should be performed after major Raspberry Pi networking, streaming, or Game Manager changes.

---

# Repository Cleanup Recommendations

This section is intended as a cleanup guide and can be removed from the final public README if you prefer to keep the README focused on runtime/setup documentation.

The current Raspberry repository contains production code alongside several generations of prototypes and older camera/AprilTag/ESP experiments.

## Safe to remove now

### `docs/streaming.md`

Remove after this information is merged into `README.md`.

```bash
rm docs/streaming.md
rmdir docs 2>/dev/null || true
```

### `scripts/carConnect.py`

Recommended removal.

Reason:

- superseded by `ESPClient.py`
- robot communication is now managed through `EspManager.py` and `ESPClient.py`
- not part of the current startup path

### `scripts/backupTag.py`

Recommended removal or archival.

Reason:

- old AprilTag prototype
- previously relied on obsolete/missing experimental code
- not part of current runtime

### `scripts/combinedCam.py`

Recommended removal or archival.

Reason:

- old combined camera/control experiment
- current production camera path is `rpicam-vid -> MPEG-TS -> GStreamer -> Janus`
- not part of startup

## Probably safe to remove after confirming no references

### `scripts/ESPClientNew.py`

Likely obsolete duplicate-generation code.

Production currently uses:

```text
scripts/ESPClient.py
```

Check before deleting:

```bash
git grep -n "ESPClientNew"
```

If nothing in active code imports or references it, remove it.

### `scripts/EspManagerNew.py`

Likely obsolete duplicate-generation code.

Production startup explicitly uses:

```text
scripts/EspManager.py
```

Check:

```bash
git grep -n "EspManagerNew"
```

If nothing active references it, remove it.

## Archive or remove depending on future charging work

The following appear to belong to AprilTag/autonomous charging experiments rather than the current game runtime:

```text
scripts/apriltagLiveFeed.py
scripts/backTest.py
scripts/FinalAprilTag.py
```

If autonomous charging is still an active planned feature, move these to a clearly named experimental directory rather than deleting them immediately.

For example:

```text
experiments/apriltag/
```

If the feature has been abandoned, delete them and rely on Git history.

## Keep temporarily

### `scripts/cleanCode.py`

Do not delete yet if an MJPEG spectator stream is still planned.

It is no longer part of the production player-stream architecture, but it remains useful as:

- a reference Picamera2/MJPEG implementation
- a low-latency camera diagnostic
- potential reference code for a future spectator output

Important limitation:

`cleanCode.py` and the Janus `rpicam-vid` pipeline cannot currently run simultaneously because both attempt to acquire the IMX219.

The eventual spectator architecture should use one camera capture pipeline and branch output to multiple consumers rather than starting a second camera owner.

A reasonable intermediate cleanup would be:

```text
scripts/legacy/cleanCode.py
```

## Directories to inspect before removing

### `streamingTesting/`

Likely removable now that Janus streaming is integrated into production.

Inspect first:

```bash
find streamingTesting -maxdepth 3 -type f | sort
```

If it only contains POC/testing files duplicated by the production Janus setup, remove it.

### `testing_scripts/`

Do not delete blindly.

Inspect:

```bash
find testing_scripts -maxdepth 3 -type f | sort
```

Useful repeatable tests may still belong in the repository.

### `scripts/archive/`

Usually safe to remove because Git history already preserves old source.

If the directory contains files that are still useful as examples/reference, either:

- document why they remain, or
- move them into a clearly named `experiments/` directory

Otherwise remove the archive directory.

---

# Cleanup Verification Commands

Before deleting legacy files, check whether anything still references them:

```bash
git grep -nE \
'ESPClientNew|EspManagerNew|FinalAprilTag|apriltagLiveFeed|backTest|backupTag|carConnect|combinedCam' \
-- ':!README.md'
```

For an individual file:

```bash
git grep -n "ESPClientNew"
```

or:

```bash
git grep -n "EspManagerNew"
```

If the only match is the file itself or old documentation, that is strong evidence that it is not part of the active runtime.

The current production runtime should only require the following major application files:

```text
start_soccer_robot.sh
stop_soccer_robot.sh

scripts/EspManager.py
scripts/ESPClient.py
scripts/GmServerPi.py
scripts/ControllerPi.py

scripts/start_streaming.sh
scripts/stop_streaming.sh
scripts/install_streaming_runtime.sh

config/janus/
requirements.txt
```

plus any intentionally retained display, hardware, testing, or future-feature code.

---

# Suggested Cleanup Target

A cleaner repository could eventually resemble:

```text
Raspberry-Pi/
|
+-- README.md
+-- requirements.txt
+-- start_soccer_robot.sh
+-- stop_soccer_robot.sh
|
+-- config/
|   +-- janus/
|       +-- janus.plugin.streaming.jcfg
|       +-- janus.transport.http.jcfg
|
+-- scripts/
|   +-- EspManager.py
|   +-- ESPClient.py
|   +-- GmServerPi.py
|   +-- ControllerPi.py
|   +-- start_streaming.sh
|   +-- stop_streaming.sh
|   +-- install_streaming_runtime.sh
|
+-- experiments/
|   +-- apriltag/
|   +-- legacy_mjpeg/
|
+-- testing_scripts/
|
+-- logs/
```

The goal is to make it immediately obvious which files are production runtime, which are experiments, and which are tests.

