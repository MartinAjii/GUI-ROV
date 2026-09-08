"""Record existing camera frames without opening a second camera device."""
import logging
import os
from pathlib import Path
import re
import shutil
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

RECORDINGS_DIR = (Path.home() / 'Videos' / 'GUI-ROV').resolve()
MIN_FREE_BYTES = 512 * 1024 * 1024
NAME_PATTERN = re.compile(r'cam[12]_\d{8}T\d{6}Z_[a-f0-9]{8}\.avi')


class Recorder:
    def __init__(self, camera_id, camera, directory=None):
        self.camera_id = camera_id
        self.camera = camera
        self.directory = Path(directory if directory is not None else RECORDINGS_DIR)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.active = False
        self.filename = None
        self.error = None
        self.started = 0
        self.duration = 0

    def status(self):
        with self.lock:
            return dict(camera=self.camera_id, recording=self.active,
                        filename=self.filename, error=self.error,
                        duration_seconds=round(time.monotonic() - self.started if self.active else self.duration, 1))

    def start(self):
        with self.lock:
            if self.active:
                return self.status()  # Idempotent for retries/multiple browser tabs.
            frame = self.camera.get_frame(max_age=2)
            if frame is None:
                raise HTTPException(409, 'Kamera belum tersambung atau tidak mengirim frame baru.')
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                if shutil.disk_usage(self.directory).free < MIN_FREE_BYTES:
                    raise HTTPException(507, 'Sisa penyimpanan kurang dari 512 MB.')
                name = f'{self.camera_id}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}.avi'
                path = self.directory / name
                h, w = frame.shape[:2]
                fps = max(1, min(30, float(self.camera.fps)))
                writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), fps, (w, h))
                if not writer.isOpened():
                    writer.release()
                    path.unlink(missing_ok=True)
                    raise HTTPException(500, 'Video writer gagal dibuka. Periksa codec dan izin folder recordings.')
            except OSError as exc:
                raise HTTPException(500, 'Folder recordings tidak dapat ditulis.') from exc
            self.filename, self.error = name, None
            self.started, self.duration = time.monotonic(), 0
            self.stop_event = threading.Event()
            self.active = True
            self.thread = threading.Thread(target=self._record, args=(writer, fps, (w, h)), daemon=True)
            self.thread.start()
            return self.status()

    def _record(self, writer, fps, size):
        next_frame = time.monotonic()
        disk_check = 0
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now >= disk_check:
                    if shutil.disk_usage(self.directory).free < MIN_FREE_BYTES:
                        raise RuntimeError('Rekaman dihentikan: sisa penyimpanan kurang dari 512 MB.')
                    disk_check = now + 1
                frame = self.camera.get_frame(max_age=2)
                if frame is None:
                    raise RuntimeError('Rekaman dihentikan: kamera terputus atau frame tidak diperbarui.')
                if (frame.shape[1], frame.shape[0]) != size:
                    frame = cv2.resize(frame, size)
                writer.write(frame)
                next_frame += 1 / fps
                # Avoid catch-up bursts when the encoder falls behind.
                next_frame = max(next_frame, time.monotonic())
                self.stop_event.wait(max(0, next_frame - time.monotonic()))
        except Exception as exc:
            logging.exception('Camera recording failed')
            with self.lock:
                self.error = str(exc)
        finally:
            writer.release()  # Finalize AVI before making it downloadable.
            with self.lock:
                self.duration = time.monotonic() - self.started
                self.active = False

    def stop(self):
        with self.lock:
            thread = self.thread
            self.stop_event.set()
        if thread:
            thread.join(timeout=10)
            if thread.is_alive():
                raise HTTPException(503, 'Video masih diselesaikan. Coba Stop lagi.')
        return self.status()


def build_recording_router(cameras, directory=None):
    directory = Path(directory if directory is not None else RECORDINGS_DIR).resolve()
    router = APIRouter(prefix='/api/recordings')
    recorders = {key: Recorder(key, camera, directory) for key, camera in cameras.items()}

    def get_recorder(camera_id):
        if camera_id not in recorders:
            raise HTTPException(404, 'Kamera tidak ditemukan.')
        return recorders[camera_id]

    @router.get('')
    def status_and_files():
        active_names = {r.filename for r in recorders.values() if r.status()['recording']}
        files = []
        if directory.exists():
            for path in sorted(directory.glob('*.avi'), reverse=True):
                if NAME_PATTERN.fullmatch(path.name) and path.name not in active_names and path.is_file():
                    files.append(dict(filename=path.name, size_bytes=path.stat().st_size))
        return dict(cameras={key: r.status() for key, r in recorders.items()}, files=files,
                    storage='laptop', output_directory=str(directory))

    @router.post('/{camera_id}/start')
    def start(camera_id: str):
        return get_recorder(camera_id).start()

    @router.post('/{camera_id}/stop')
    def stop(camera_id: str):
        return get_recorder(camera_id).stop()

    @router.get('/download/{filename}')
    def download(filename: str):
        if not NAME_PATTERN.fullmatch(filename):
            raise HTTPException(404, 'Rekaman tidak ditemukan.')
        if any(r.status()['recording'] and r.filename == filename for r in recorders.values()):
            raise HTTPException(409, 'Hentikan rekaman sebelum mengunduh.')
        path = directory / filename
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404, 'Rekaman tidak ditemukan.')
        return FileResponse(path, filename=filename, media_type='video/x-msvideo')

    return router, recorders
