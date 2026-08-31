#!/usr/bin/env bash

set -euo pipefail

# ------------------------------------------------------------
# Soccer Robots Raspberry Pi startup script
# ------------------------------------------------------------

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

LOG_DIR="$PROJECT_DIR/logs"

ESP_MANAGER="$PROJECT_DIR/scripts/EspManager.py"
GM_SERVER="$PROJECT_DIR/scripts/GmServerPi.py"
CONTROLLER="$PROJECT_DIR/scripts/ControllerPi.py"


# ------------------------------------------------------------
# VERIFY VIRTUAL ENVIRONMENT
# ------------------------------------------------------------

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python virtual environment not found:"
    echo "$PYTHON"
    echo
    echo "Expected .venv to exist inside:"
    echo "$PROJECT_DIR"
    exit 1
fi


# ------------------------------------------------------------
# CREATE LOG DIRECTORY
# ------------------------------------------------------------

mkdir -p "$LOG_DIR"


# ------------------------------------------------------------
# PREVENT DUPLICATE PROCESSES
# ------------------------------------------------------------

if pgrep -f "$ESP_MANAGER" > /dev/null; then
    echo "ERROR: EspManager.py is already running."
    echo "Stop the existing Soccer Robots processes before starting again."
    exit 1
fi

if pgrep -f "$GM_SERVER" > /dev/null; then
    echo "ERROR: GmServerPi.py is already running."
    echo "Stop the existing Soccer Robots processes before starting again."
    exit 1
fi

if pgrep -f "$CONTROLLER" > /dev/null; then
    echo "ERROR: ControllerPi.py is already running."
    echo "Stop the existing Soccer Robots processes before starting again."
    exit 1
fi


# ------------------------------------------------------------
# REMOVE STALE UNIX SOCKETS
# ------------------------------------------------------------

rm -f /tmp/gmESPSocket
rm -f /tmp/controlESPSocket


# ------------------------------------------------------------
# CLEAR OLD LOGS
# ------------------------------------------------------------

: > "$LOG_DIR/esp.txt"
: > "$LOG_DIR/GMServer.txt"
: > "$LOG_DIR/Controller.txt"


# ------------------------------------------------------------
# START ESP MANAGER
# ------------------------------------------------------------

echo "Starting EspManager.py"

nohup "$PYTHON" "$ESP_MANAGER" \
    > "$LOG_DIR/esp.txt" \
    2>&1 &

ESP_PID=$!

sleep 2


# Verify EspManager survived startup
if ! kill -0 "$ESP_PID" 2>/dev/null; then
    echo "ERROR: EspManager.py failed to start."
    echo
    cat "$LOG_DIR/esp.txt"
    exit 1
fi


# ------------------------------------------------------------
# START GAME MANAGER SERVER
# ------------------------------------------------------------

echo "Starting GmServerPi.py"

nohup "$PYTHON" "$GM_SERVER" \
    > "$LOG_DIR/GMServer.txt" \
    2>&1 &

GM_PID=$!

sleep 2


# Verify Game Manager survived startup
if ! kill -0 "$GM_PID" 2>/dev/null; then
    echo "ERROR: GmServerPi.py failed to start."
    echo
    cat "$LOG_DIR/GMServer.txt"

    kill "$ESP_PID" 2>/dev/null || true

    exit 1
fi


# ------------------------------------------------------------
# START CONTROLLER SERVER
# ------------------------------------------------------------

echo "Starting ControllerPi.py"

nohup "$PYTHON" "$CONTROLLER" \
    > "$LOG_DIR/Controller.txt" \
    2>&1 &

CONTROLLER_PID=$!

sleep 2


# Verify Controller survived startup
if ! kill -0 "$CONTROLLER_PID" 2>/dev/null; then
    echo "ERROR: ControllerPi.py failed to start."
    echo
    cat "$LOG_DIR/Controller.txt"

    kill "$GM_PID" 2>/dev/null || true
    kill "$ESP_PID" 2>/dev/null || true

    exit 1
fi


# ------------------------------------------------------------
# SUCCESS
# ------------------------------------------------------------

echo
echo "Soccer Robots services started successfully."
echo
echo "EspManager PID:   $ESP_PID"
echo "GameManager PID:  $GM_PID"
echo "Controller PID:   $CONTROLLER_PID"
echo
echo "Logs:"
echo "  $LOG_DIR/esp.txt"
echo "  $LOG_DIR/GMServer.txt"
echo "  $LOG_DIR/Controller.txt"
