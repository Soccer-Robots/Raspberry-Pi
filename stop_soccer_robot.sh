#!/usr/bin/env bash

set -u

# ------------------------------------------------------------
# Soccer Robots Raspberry Pi shutdown script
# ------------------------------------------------------------

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ESP_MANAGER="$PROJECT_DIR/scripts/EspManager.py"
GM_SERVER="$PROJECT_DIR/scripts/GmServerPi.py"
CONTROLLER="$PROJECT_DIR/scripts/ControllerPi.py"

STREAM_STOP="$PROJECT_DIR/scripts/stop_streaming.sh"


echo
echo "=================================="
echo " Stopping Soccer Robots"
echo "=================================="
echo


# ------------------------------------------------------------
# STOP STREAMING
# ------------------------------------------------------------

if [ -x "$STREAM_STOP" ]; then

    echo "[1/4] Stopping streaming stack..."

    "$STREAM_STOP" || true

else

    echo "[1/4] Streaming stop script not found."

fi


# ------------------------------------------------------------
# STOP CONTROLLER
# ------------------------------------------------------------

echo
echo "[2/4] Stopping ControllerPi.py..."

if pgrep -f "$CONTROLLER" > /dev/null; then

    pkill -f "$CONTROLLER" || true

    sleep 1

    if pgrep -f "$CONTROLLER" > /dev/null; then
        echo "ControllerPi.py did not stop cleanly. Forcing shutdown."
        pkill -9 -f "$CONTROLLER" || true
    else
        echo "ControllerPi.py stopped."
    fi

else

    echo "ControllerPi.py is not running."

fi


# ------------------------------------------------------------
# STOP GAME MANAGER
# ------------------------------------------------------------

echo
echo "[3/4] Stopping GmServerPi.py..."

if pgrep -f "$GM_SERVER" > /dev/null; then

    pkill -f "$GM_SERVER" || true

    sleep 1

    if pgrep -f "$GM_SERVER" > /dev/null; then
        echo "GmServerPi.py did not stop cleanly. Forcing shutdown."
        pkill -9 -f "$GM_SERVER" || true
    else
        echo "GmServerPi.py stopped."
    fi

else

    echo "GmServerPi.py is not running."

fi


# ------------------------------------------------------------
# STOP ESP MANAGER
# ------------------------------------------------------------

echo
echo "[4/4] Stopping EspManager.py..."

if pgrep -f "$ESP_MANAGER" > /dev/null; then

    pkill -f "$ESP_MANAGER" || true

    sleep 1

    if pgrep -f "$ESP_MANAGER" > /dev/null; then
        echo "EspManager.py did not stop cleanly. Forcing shutdown."
        pkill -9 -f "$ESP_MANAGER" || true
    else
        echo "EspManager.py stopped."
    fi

else

    echo "EspManager.py is not running."

fi


# ------------------------------------------------------------
# CLEAN RUNTIME FILES
# ------------------------------------------------------------

echo
echo "Cleaning runtime files..."

rm -f /tmp/gmESPSocket
rm -f /tmp/controlESPSocket
rm -f /tmp/shared_timer


# ------------------------------------------------------------
# SUCCESS
# ------------------------------------------------------------

echo
echo "=================================="
echo " Soccer Robots stopped"
echo "=================================="
echo
