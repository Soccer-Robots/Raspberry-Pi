#!/usr/bin/env bash

set -euo pipefail

# ------------------------------------------------------------
# Soccer Robots streaming startup
# ------------------------------------------------------------

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

JANUS_DIR="$HOME/soccerrobots-runtime/janus"
JANUS_BIN="$JANUS_DIR/bin/janus"
JANUS_CONFIG="$JANUS_DIR/etc/janus"

LOG_DIR="$PROJECT_DIR/logs"
RUN_DIR="/tmp/soccerrobots-streaming"

JANUS_LOG="$LOG_DIR/janus.txt"
CAMERA_LOG="$LOG_DIR/camera_stream.txt"

JANUS_PID_FILE="$RUN_DIR/janus.pid"
CAMERA_PGID_FILE="$RUN_DIR/camera.pgid"


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

cleanup_failed_start() {

    if [ -f "$CAMERA_PGID_FILE" ]; then

        CAMERA_PGID="$(cat "$CAMERA_PGID_FILE")"

        if [ -n "$CAMERA_PGID" ]; then
            kill -- "-$CAMERA_PGID" 2>/dev/null || true
        fi

        rm -f "$CAMERA_PGID_FILE"
    fi


    if [ -f "$JANUS_PID_FILE" ]; then

        JANUS_PID="$(cat "$JANUS_PID_FILE")"

        if kill -0 "$JANUS_PID" 2>/dev/null; then
            kill "$JANUS_PID" 2>/dev/null || true
        fi

        rm -f "$JANUS_PID_FILE"
    fi
}


# ------------------------------------------------------------
# CREATE DIRECTORIES
# ------------------------------------------------------------

mkdir -p "$LOG_DIR"
mkdir -p "$RUN_DIR"


# ------------------------------------------------------------
# VERIFY REQUIREMENTS
# ------------------------------------------------------------

if [ ! -x "$JANUS_BIN" ]; then
    echo "ERROR: Janus binary not found:"
    echo "$JANUS_BIN"
    exit 1
fi


if [ ! -d "$JANUS_CONFIG" ]; then
    echo "ERROR: Janus configuration directory not found:"
    echo "$JANUS_CONFIG"
    exit 1
fi


for COMMAND in \
    rpicam-vid \
    gst-launch-1.0 \
    setsid \
    ss
do

    if ! command -v "$COMMAND" > /dev/null 2>&1; then
        echo "ERROR: Required command not found:"
        echo "$COMMAND"
        exit 1
    fi

done


# ------------------------------------------------------------
# PREVENT DUPLICATE STREAMING STACK
# ------------------------------------------------------------

if pgrep -f "$JANUS_BIN" > /dev/null; then
    echo "ERROR: Soccer Robots Janus is already running."
    exit 1
fi


if pgrep -x rpicam-vid > /dev/null; then
    echo "ERROR: rpicam-vid is already running."
    echo "The camera may already be in use."
    exit 1
fi


if pgrep -f "gst-launch-1.0" > /dev/null; then
    echo "ERROR: GStreamer is already running."
    exit 1
fi


# ------------------------------------------------------------
# CLEAR RUNTIME STATE / LOGS
# ------------------------------------------------------------

rm -f "$JANUS_PID_FILE"
rm -f "$CAMERA_PGID_FILE"

: > "$JANUS_LOG"
: > "$CAMERA_LOG"


echo
echo "=================================="
echo " Soccer Robots Streaming"
echo "=================================="
echo


# ------------------------------------------------------------
# START JANUS
# ------------------------------------------------------------

echo "[1/2] Starting Janus..."


nohup "$JANUS_BIN" \
    -F "$JANUS_CONFIG" \
    > "$JANUS_LOG" \
    2>&1 &


JANUS_PID=$!

echo "$JANUS_PID" > "$JANUS_PID_FILE"


sleep 2


if ! kill -0 "$JANUS_PID" 2>/dev/null; then

    echo "ERROR: Janus exited during startup."
    echo
    tail -n 50 "$JANUS_LOG"

    cleanup_failed_start
    exit 1
fi


if ! ss -ltn | grep -q ':8088 '; then

    echo "ERROR: Janus is running, but port 8088 is not listening."
    echo
    tail -n 50 "$JANUS_LOG"

    cleanup_failed_start
    exit 1
fi


echo "Janus started."
echo "PID: $JANUS_PID"


# ------------------------------------------------------------
# START CAMERA PIPELINE
# ------------------------------------------------------------

echo
echo "[2/2] Starting camera pipeline..."


nohup setsid bash -c '
    set -o pipefail

    rpicam-vid \
        --camera 0 \
        --width 640 \
        --height 480 \
        --framerate 30 \
        --codec libav \
        --libav-format mpegts \
        --bitrate 1000000 \
        --intra 10 \
        --nopreview \
        --timeout 0 \
        --output - \
    | gst-launch-1.0 \
        fdsrc \
        ! tsdemux \
        ! h264parse \
        ! rtph264pay pt=96 config-interval=-1 \
        ! udpsink host=127.0.0.1 port=5006 sync=false async=false
' > "$CAMERA_LOG" 2>&1 &


CAMERA_PGID=$!

echo "$CAMERA_PGID" > "$CAMERA_PGID_FILE"


sleep 3


if ! kill -0 "$CAMERA_PGID" 2>/dev/null; then

    echo "ERROR: Camera pipeline exited during startup."
    echo
    tail -n 50 "$CAMERA_LOG"

    cleanup_failed_start
    exit 1
fi


if ! pgrep -x rpicam-vid > /dev/null; then

    echo "ERROR: rpicam-vid did not start."
    echo
    tail -n 50 "$CAMERA_LOG"

    cleanup_failed_start
    exit 1
fi


if ! pgrep -f "gst-launch-1.0" > /dev/null; then

    echo "ERROR: GStreamer did not start."
    echo
    tail -n 50 "$CAMERA_LOG"

    cleanup_failed_start
    exit 1
fi


echo "Camera pipeline started."
echo "Process group: $CAMERA_PGID"


# ------------------------------------------------------------
# SUCCESS
# ------------------------------------------------------------

echo
echo "=================================="
echo " Streaming started successfully"
echo "=================================="
echo
echo "Janus:"
echo "  http://10.42.0.1:8088/janus"
echo
echo "Camera:"
echo "  IMX219"
echo "  640x480 @ 30 FPS"
echo "  H.264 / MPEG-TS"
echo "  RTP -> 127.0.0.1:5006"
echo "  Janus mountpoint: 43"
echo
echo "Janus PID:"
echo "  $JANUS_PID"
echo
echo "Camera process group:"
echo "  $CAMERA_PGID"
echo
echo "Logs:"
echo "  $JANUS_LOG"
echo "  $CAMERA_LOG"