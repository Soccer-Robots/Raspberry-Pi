#!/usr/bin/env bash

set -euo pipefail

# ------------------------------------------------------------
# Soccer Robots Janus Streaming Runtime Installer
# ------------------------------------------------------------

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RUNTIME_ROOT="$HOME/soccerrobots-runtime"
JANUS_PREFIX="$RUNTIME_ROOT/janus"

BUILD_ROOT="$HOME/soccerrobots-build"
JANUS_SOURCE="$BUILD_ROOT/janus-gateway"

JANUS_REPO="https://github.com/meetecho/janus-gateway.git"

# Known-good Janus version used during Soccer Robots development.
JANUS_COMMIT="4602fcc5315b77dce2a5d8363a4286ac672183b1"

CONFIG_SOURCE="$PROJECT_DIR/config/janus"


echo
echo "============================================"
echo " Soccer Robots Streaming Runtime Installer"
echo "============================================"
echo


# ------------------------------------------------------------
# VERIFY CONFIG FILES
# ------------------------------------------------------------

if [ ! -f "$CONFIG_SOURCE/janus.plugin.streaming.jcfg" ]; then
    echo "ERROR: Missing Janus streaming configuration:"
    echo "$CONFIG_SOURCE/janus.plugin.streaming.jcfg"
    exit 1
fi


if [ ! -f "$CONFIG_SOURCE/janus.transport.http.jcfg" ]; then
    echo "ERROR: Missing Janus HTTP configuration:"
    echo "$CONFIG_SOURCE/janus.transport.http.jcfg"
    exit 1
fi


# ------------------------------------------------------------
# INSTALL SYSTEM DEPENDENCIES
# ------------------------------------------------------------

echo "[1/7] Installing system dependencies..."

sudo apt update

sudo apt install -y \
    git \
    build-essential \
    autoconf \
    automake \
    libtool \
    pkg-config \
    libglib2.0-dev \
    zlib1g-dev \
    libssl-dev \
    libjansson-dev \
    libconfig-dev \
    libnice-dev \
    libsrtp2-dev \
    libmicrohttpd-dev \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good


# ------------------------------------------------------------
# CREATE DIRECTORIES
# ------------------------------------------------------------

echo
echo "[2/7] Creating build and runtime directories..."

mkdir -p "$BUILD_ROOT"
mkdir -p "$RUNTIME_ROOT"


# ------------------------------------------------------------
# DOWNLOAD JANUS
# ------------------------------------------------------------

echo
echo "[3/7] Preparing Janus source..."

if [ ! -d "$JANUS_SOURCE/.git" ]; then

    git clone \
        "$JANUS_REPO" \
        "$JANUS_SOURCE"

fi


cd "$JANUS_SOURCE"

git fetch --all --tags

git checkout --force "$JANUS_COMMIT"


# ------------------------------------------------------------
# CONFIGURE JANUS
# ------------------------------------------------------------

echo
echo "[4/7] Configuring Janus..."

sh autogen.sh

./configure \
    --prefix="$JANUS_PREFIX" \
    --disable-websockets \
    --disable-data-channels \
    --disable-rabbitmq \
    --disable-mqtt


# ------------------------------------------------------------
# BUILD JANUS
# ------------------------------------------------------------

echo
echo "[5/7] Building Janus..."

make -j2


# ------------------------------------------------------------
# INSTALL JANUS
# ------------------------------------------------------------

echo
echo "[6/7] Installing Janus..."

make install

# This is a fresh runtime install. Generate the standard
# Janus configuration first, then replace the files that
# Soccer Robots customizes.

make configs


# ------------------------------------------------------------
# INSTALL SOCCER ROBOTS CONFIGURATION
# ------------------------------------------------------------

echo
echo "[7/7] Installing Soccer Robots configuration..."

cp \
    "$CONFIG_SOURCE/janus.plugin.streaming.jcfg" \
    "$JANUS_PREFIX/etc/janus/janus.plugin.streaming.jcfg"

cp \
    "$CONFIG_SOURCE/janus.transport.http.jcfg" \
    "$JANUS_PREFIX/etc/janus/janus.transport.http.jcfg"


echo
echo "Verifying installation..."


if [ ! -x "$JANUS_PREFIX/bin/janus" ]; then

    echo "ERROR: Janus binary was not installed."
    exit 1

fi


"$JANUS_PREFIX/bin/janus" --version


echo
echo "Checking GStreamer..."

gst-inspect-1.0 tsdemux > /dev/null
gst-inspect-1.0 h264parse > /dev/null
gst-inspect-1.0 rtph264pay > /dev/null


echo
echo "============================================"
echo " Streaming runtime installed successfully"
echo "============================================"
echo
echo "Janus:"
echo "  $JANUS_PREFIX/bin/janus"
echo
echo "Configuration:"
echo "  $JANUS_PREFIX/etc/janus"
echo
echo "Camera RTP:"
echo "  UDP 127.0.0.1:5006"
echo
echo "Janus HTTP:"
echo "  http://10.42.0.1:8088/janus"
echo
echo "Streaming mountpoint:"
echo "  43"
echo
