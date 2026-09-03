# Soccer Robots Video Streaming

Soccer Robots uses Janus WebRTC for the low-latency video feed shown to active players.

## Architecture

The Raspberry Pi camera is captured once and encoded as H.264.

```text
IMX219 Camera
    |
    v
rpicam-vid
    |
    | H.264 / MPEG-TS
    v
GStreamer
    |
    | RTP/H.264
    | UDP 127.0.0.1:5006
    v
Janus Streaming Plugin
    |
    | WebRTC
    v
Soccer Robots Client
