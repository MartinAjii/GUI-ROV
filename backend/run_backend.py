"""
run_backend.py
---------------------------------------------------------------
Menjalankan camera_stream.py (Flask, di thread terpisah) dan
mavlink_bridge.py (asyncio, di thread utama) sekaligus, supaya
cuma perlu satu perintah di Raspberry Pi:

    python3 run_backend.py

Kalau mau debug salah satu bagian saja, jalankan filenya langsung:
    python3 camera_stream.py
    python3 mavlink_bridge.py
---------------------------------------------------------------
"""

import asyncio
import threading

import config
import camera_stream
import mavlink_bridge


def start_camera_server():
    camera_stream.app.run(
        host=config.CAMERA_HTTP_HOST,
        port=config.CAMERA_HTTP_PORT,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    threading.Thread(target=start_camera_server, daemon=True).start()
    print(f"[CAM] Streaming di http://{config.CAMERA_HTTP_HOST}:{config.CAMERA_HTTP_PORT}/stream/bottom")
    print(f"[CAM] Streaming di http://{config.CAMERA_HTTP_HOST}:{config.CAMERA_HTTP_PORT}/stream/wall")

    asyncio.run(mavlink_bridge.main())
