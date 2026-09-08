"""One bounded MJPEG connection per Pi camera, shared by preview and recording."""
import logging
import threading
import time

import cv2
import httpx
import numpy as np

MAX_FRAME_BYTES = 4 * 1024 * 1024


def jpeg_frames(chunks):
    buffer = bytearray()
    for chunk in chunks:
        buffer.extend(chunk)
        while True:
            start = buffer.find(b'\xff\xd8')
            if start < 0:
                buffer[:] = buffer[-1:]
                break
            if start:
                del buffer[:start]
            end = buffer.find(b'\xff\xd9', 2)
            if end < 0:
                if len(buffer) > MAX_FRAME_BYTES:
                    raise ValueError('Frame MJPEG melebihi batas 4 MB.')
                break
            if end + 2 > MAX_FRAME_BYTES:
                raise ValueError('Frame MJPEG melebihi batas 4 MB.')
            yield bytes(buffer[:end + 2])
            del buffer[:end + 2]


class RemoteCamera:
    def __init__(self, url, fps=15):
        self.url = url
        self.fps = fps
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.latest_frame = None
        self.latest_jpeg = None
        self.latest_at = 0
        self.sequence = 0

    def start(self):
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)

    def _read(self):
        while not self.stop_event.is_set():
            try:
                # Ignore OS proxy settings for the direct LAN camera connection.
                with httpx.stream('GET', self.url, timeout=2, trust_env=False) as response:
                    response.raise_for_status()
                    for jpeg in jpeg_frames(response.iter_bytes()):
                        if self.stop_event.is_set():
                            return
                        frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is None:
                            continue
                        with self.lock:
                            self.latest_frame = frame
                            self.latest_jpeg = jpeg
                            self.latest_at = time.monotonic()
                            self.sequence += 1
            except (httpx.HTTPError, ValueError, cv2.error) as exc:
                logging.warning('Camera stream unavailable: %s: %s', self.url, exc)
            self.stop_event.wait(1)

    def get_frame(self, max_age=2):
        with self.lock:
            if self.latest_frame is None or time.monotonic() - self.latest_at > max_age:
                return None
            return self.latest_frame.copy()

    def get_jpeg(self):
        with self.lock:
            if self.latest_jpeg is None or time.monotonic() - self.latest_at > 2:
                return self.sequence, None
            return self.sequence, self.latest_jpeg
