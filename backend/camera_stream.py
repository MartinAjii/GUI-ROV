"""
camera_stream.py
---------------------------------------------------------------
Streaming 2 kamera (BOTTOM & WALL) yang tersambung ke Raspberry Pi,
supaya bisa ditonton dari browser di laptop topside lewat LAN
(lewat hAP lite), tanpa perlu getUserMedia (yang cuma bisa akses
kamera yang tersambung langsung ke perangkat browser berjalan).

Dashboard mengambil feed ini lewat tag <img> yang menunjuk ke:
    http://<ip-raspberry-pi>:5000/stream/bottom
    http://<ip-raspberry-pi>:5000/stream/wall

Jalankan:
    python3 camera_stream.py

Cek dulu kamera terdeteksi dengan benar:
    v4l2-ctl --list-devices
lalu sesuaikan CAMERA_BOTTOM_INDEX / CAMERA_WALL_INDEX di config.py.
---------------------------------------------------------------
"""

import threading
import time

import cv2
from flask import Flask, Response

import config

app = Flask(__name__)


class CameraFeed:
    """Membaca satu kamera di thread terpisah supaya beberapa klien
    (atau jsQR di sisi dashboard yang polling terus) tidak saling
    menunggu buka device kamera dari awal."""

    def __init__(self, index, width, height, fps):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        return self

    def _open(self):
        cap = cv2.VideoCapture(self.index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        return cap

    def _loop(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                print(f"[CAM {self.index}] Membuka kamera...")
                self.cap = self._open()
                if not self.cap.isOpened():
                    print(f"[CAM {self.index}] Gagal buka kamera, coba lagi 2 detik.")
                    time.sleep(2)
                    continue

            ok, frame = self.cap.read()
            if not ok:
                print(f"[CAM {self.index}] Gagal baca frame, buka ulang kamera.")
                self.cap.release()
                self.cap = None
                time.sleep(1)
                continue

            ok, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config.CAMERA_JPEG_QUALITY]
            )
            if ok:
                with self.lock:
                    self.frame = jpeg.tobytes()

    def get_jpeg(self):
        with self.lock:
            return self.frame


bottom_feed = CameraFeed(
    config.CAMERA_BOTTOM_INDEX, config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS
).start()

wall_feed = CameraFeed(
    config.CAMERA_WALL_INDEX, config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS
).start()


def mjpeg_generator(feed: CameraFeed):
    while True:
        jpeg = feed.get_jpeg()
        if jpeg is None:
            time.sleep(0.1)
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        )
        time.sleep(1.0 / max(1, config.CAMERA_FPS))


@app.route("/stream/bottom")
def stream_bottom():
    return Response(
        mjpeg_generator(bottom_feed),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/stream/wall")
def stream_wall():
    return Response(
        mjpeg_generator(wall_feed),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/health")
def health():
    return {
        "bottom_ok": bottom_feed.get_jpeg() is not None,
        "wall_ok": wall_feed.get_jpeg() is not None,
    }


if __name__ == "__main__":
    print(f"[CAM] Streaming di http://{config.CAMERA_HTTP_HOST}:{config.CAMERA_HTTP_PORT}/stream/bottom")
    print(f"[CAM] Streaming di http://{config.CAMERA_HTTP_HOST}:{config.CAMERA_HTTP_PORT}/stream/wall")
    app.run(host=config.CAMERA_HTTP_HOST, port=config.CAMERA_HTTP_PORT, threaded=True)
