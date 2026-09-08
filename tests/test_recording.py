import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from laptop_recorder import recording


class Camera:
    fps = 15
    connected = True

    def get_frame(self, max_age=None):
        if not self.connected:
            return None
        return np.full((48, 64, 3), int(time.monotonic() * 80) % 255, dtype=np.uint8)


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.patch = patch.object(recording, 'RECORDINGS_DIR', self.directory)
        self.patch.start()
        self.cameras = {'cam1': Camera(), 'cam2': Camera()}
        router, self.recorders = recording.build_recording_router(self.cameras)
        for recorder in self.recorders.values():
            recorder.directory = self.directory
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        for recorder in self.recorders.values():
            recorder.stop()
        self.client.close()
        self.patch.stop()
        self.tmp.cleanup()

    def test_two_cameras_finalize_download_and_retry(self):
        names = []
        for camera in self.cameras:
            response = self.client.post(f'/api/recordings/{camera}/start')
            self.assertEqual(response.status_code, 200, response.text)
            name = response.json()['filename']
            names.append(name)
            self.assertEqual(self.client.post(f'/api/recordings/{camera}/start').json()['filename'], name)
            self.assertEqual(self.client.get(f'/api/recordings/download/{name}').status_code, 409)
        self.assertEqual(self.client.get('/api/recordings').json()['files'], [])
        time.sleep(.3)
        for camera, name in zip(self.cameras, names):
            status = self.client.post(f'/api/recordings/{camera}/stop').json()
            self.assertFalse(status['recording'])
            self.assertIsNone(status['error'])
            cap = cv2.VideoCapture(str(self.directory / name))
            ok, frame = cap.read()
            cap.release()
            self.assertTrue(ok)
            self.assertEqual(frame.shape[:2], (48, 64))
            response = self.client.get(f'/api/recordings/download/{name}')
            self.assertEqual(response.status_code, 200)
            self.assertGreater(len(response.content), 100)
            self.assertFalse(self.client.post(f'/api/recordings/{camera}/stop').json()['recording'])
        self.assertEqual(len(self.client.get('/api/recordings').json()['files']), 2)

    def test_missing_camera_and_disk_full(self):
        self.cameras['cam1'].connected = False
        self.assertEqual(self.client.post('/api/recordings/cam1/start').status_code, 409)
        self.assertEqual(self.client.post('/api/recordings/unknown/start').status_code, 404)
        with patch.object(recording.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            self.assertEqual(self.client.post('/api/recordings/cam2/start').status_code, 507)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_disconnect_finalizes_and_allows_restart(self):
        self.client.post('/api/recordings/cam1/start')
        time.sleep(.15)
        self.cameras['cam1'].connected = False
        deadline = time.monotonic() + 2
        while self.recorders['cam1'].status()['recording'] and time.monotonic() < deadline:
            time.sleep(.02)
        status = self.recorders['cam1'].status()
        self.assertFalse(status['recording'])
        self.assertIn('kamera terputus', status['error'])
        self.assertEqual(self.client.get(f"/api/recordings/download/{status['filename']}").status_code, 200)
        self.cameras['cam1'].connected = True
        new = self.client.post('/api/recordings/cam1/start').json()
        self.assertNotEqual(new['filename'], status['filename'])
        self.assertIsNone(new['error'])

    def test_disk_full_during_recording(self):
        self.client.post('/api/recordings/cam1/start')
        time.sleep(.1)
        with patch.object(recording.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)):
            deadline = time.monotonic() + 2
            while self.recorders['cam1'].status()['recording'] and time.monotonic() < deadline:
                time.sleep(.02)
        status = self.recorders['cam1'].status()
        self.assertFalse(status['recording'])
        self.assertIn('penyimpanan', status['error'])

    def test_download_rejects_unrelated_files(self):
        (self.directory / 'secret.avi').write_bytes(b'private')
        self.assertEqual(self.client.get('/api/recordings/download/secret.avi').status_code, 404)
        self.assertEqual(self.client.get('/api/recordings').json()['files'], [])


if __name__ == '__main__':
    unittest.main()
