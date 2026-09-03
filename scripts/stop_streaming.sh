#!/usr/bin/env bash

set -u

# ------------------------------------------------------------
# Soccer Robots streaming shutdown
# ------------------------------------------------------------

RUN_DIR="/tmp/soccerrobots-streaming"

JANUS_PID_FILE="$RUN_DIR/janus.pid"
CAMERA_PGID_FILE="$RUN_DIR/camera.pgid"


echo
echo "=================================="
echo " Stopping Soccer Robots Streaming"
echo "=================================="
echo


# ------------------------------------------------------------
# STOP CAMERA PROCESS GROUP
# ------------------------------------------------------------

echo "[1/2] Stopping camera pipeline..."


if [ -f "$CAMERA_PGID_FILE" ]; then

    CAMERA_PGID="$(cat "$CAMERA_PGID_FILE")"


    if [ -n "$CAMERA_PGID" ] && \
       kill -0 "$CAMERA_PGID" 2>/dev/null
    then

        echo "Stopping camera process group $CAMERA_PGID..."

        kill -- "-$CAMERA_PGID" 2>/dev/null || true


        for _ in {1..20}; do

            if ! kill -0 "$CAMERA_PGID" 2>/dev/null; then
                break
            fi

            sleep 0.1
        done


        if kill -0 "$CAMERA_PGID" 2>/dev/null; then

            echo "Camera pipeline did not stop cleanly."
            echo "Forcing shutdown..."

            kill -9 -- "-$CAMERA_PGID" 2>/dev/null || true
        fi


        echo "Camera pipeline stopped."

    else

        echo "Camera pipeline is not running."

    fi


    rm -f "$CAMERA_PGID_FILE"

else

    echo "No camera process-group file found."

fi


# ------------------------------------------------------------
# STOP JANUS
# ------------------------------------------------------------

echo
echo "[2/2] Stopping Janus..."


if [ -f "$JANUS_PID_FILE" ]; then

    JANUS_PID="$(cat "$JANUS_PID_FILE")"


    if kill -0 "$JANUS_PID" 2>/dev/null; then

        echo "Stopping Janus PID $JANUS_PID..."

        kill "$JANUS_PID" 2>/dev/null || true


        for _ in {1..20}; do

            if ! kill -0 "$JANUS_PID" 2>/dev/null; then
                break
            fi

            sleep 0.1
        done


        if kill -0 "$JANUS_PID" 2>/dev/null; then

            echo "Janus did not stop cleanly."
            echo "Forcing shutdown..."

            kill -9 "$JANUS_PID" 2>/dev/null || true
        fi


        echo "Janus stopped."

    else

        echo "Janus is not running."

    fi


    rm -f "$JANUS_PID_FILE"

else

    echo "No Janus PID file found."

fi


# ------------------------------------------------------------
# CLEANUP
# ------------------------------------------------------------

rmdir "$RUN_DIR" 2>/dev/null || true


echo
echo "=================================="
echo " Streaming stopped"
echo "=================================="