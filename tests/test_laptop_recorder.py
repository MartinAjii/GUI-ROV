import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import cv2
from fastapi.testclient import TestClient
import numpy as np
from websockets.sync.server import serve

from laptop_recorder.app import create_app
from laptop_recorder.camera import jpeg_frames, RemoteCamera
from laptop_recorder.recording import Recorder


class SyntheticCamera:
    fps = 15
    stopped = False

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def get_frame(self, max_age=2):
        return np.zeros((48, 64, 3), np.uint8)

    def get_jpeg(self):
        return 0, None


class LaptopTests(unittest.TestCase):
    def test_parser_fragmented_markers(self):
        data = b'headers\r\n\xff\xd8abc\xff\xd9\r\n--frame\r\n\xff\xd8def\xff\xd9'
        self.assertEqual(list(jpeg_frames(bytes([byte]) for byte in data)),
                         [b'\xff\xd8abc\xff\xd9', b'\xff\xd8def\xff\xd9'])
        with patch('laptop_recorder.camera.MAX_FRAME_BYTES', 8):
            with self.assertRaises(ValueError):
                list(jpeg_frames([b'\xff\xd8' + b'x' * 20]))

    def test_gui_storage_origin_and_shutdown(self):
        cameras = {key: SyntheticCamera() for key in ('cam1', 'cam2')}
        with tempfile.TemporaryDirectory() as directory:
            app = create_app('http://127.0.0.1:9999', directory, cameras=cameras)
            with TestClient(app, base_url='http://127.0.0.1:8080') as client:
                self.assertEqual(client.get('/').status_code, 200)
                self.assertEqual(client.get('/js/camera-record.js').status_code, 200)
                data = client.get('/api/recordings').json()
                self.assertEqual(data['storage'], 'laptop')
                self.assertEqual(data['output_directory'], str(Path(directory).resolve()))
                self.assertEqual(client.post('/api/recordings/cam1/start', headers={'Origin':'https://other.example'}).status_code, 403)
                self.assertEqual(client.get('/', headers={'Host':'other.example'}).status_code, 400)
                self.assertEqual(client.post('/api/recordings/cam1/start').status_code, 200)
                time.sleep(.15)
            self.assertFalse(app.state.recorders['cam1'].status()['recording'])
            self.assertTrue(all(camera.stopped for camera in cameras.values()))
            files = list(Path(directory).glob('*.avi'))
            self.assertEqual(len(files), 1)
            cap = cv2.VideoCapture(str(files[0])); ok, _ = cap.read(); cap.release()
            self.assertTrue(ok)

    def test_real_mjpeg_to_laptop_disk_and_stale_frames(self):
        _, jpeg = cv2.imencode('.jpg', np.full((48, 64, 3), 128, np.uint8))
        feed = threading.Event(); feed.set()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                self.end_headers()
                try:
                    while feed.is_set():
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+jpeg.tobytes()+b'\r\n')
                        self.wfile.flush()
                        time.sleep(.04)
                except (BrokenPipeError, ConnectionResetError): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        camera = RemoteCamera(f'http://127.0.0.1:{server.server_port}/video/cam1')
        camera.start()
        try:
            deadline=time.monotonic()+3
            while camera.get_frame() is None and time.monotonic()<deadline: time.sleep(.02)
            self.assertIsNotNone(camera.get_frame())
            with tempfile.TemporaryDirectory() as directory:
                recorder = Recorder('cam1', camera, directory)
                recorder.start()
                time.sleep(.3)
                feed.clear()
                deadline=time.monotonic()+5
                while recorder.status()['recording'] and time.monotonic()<deadline: time.sleep(.05)
                recorder.stop()
                self.assertIn('kamera terputus', recorder.status()['error'])
                cap=cv2.VideoCapture(str(Path(directory)/recorder.filename))
                ok, frame=cap.read(); cap.release()
                self.assertTrue(ok)
                self.assertEqual(frame.shape[:2], (48,64))
        finally:
            feed.clear(); camera.stop(); server.shutdown(); server.server_close()

    def test_websocket_forwards_both_directions(self):
        def echo(connection):
            connection.send('{"type":"telemetry","depth":1}')
            for message in connection:
                connection.send(message)
        with serve(echo, '127.0.0.1', 0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            port=server.socket.getsockname()[1]
            cameras={key:SyntheticCamera() for key in ('cam1','cam2')}
            with tempfile.TemporaryDirectory() as directory:
                app=create_app(f'http://127.0.0.1:{port}', directory, cameras=cameras)
                with TestClient(app, base_url='http://127.0.0.1:8080') as client:
                    with client.websocket_connect('ws://127.0.0.1:8080/ws/telemetry') as ws:
                        self.assertEqual(ws.receive_json()['depth'], 1)
                        ws.send_text('{"type":"test-message"}')
                        self.assertEqual(ws.receive_text(), '{"type":"test-message"}')
            server.shutdown()


if __name__ == '__main__': unittest.main()
