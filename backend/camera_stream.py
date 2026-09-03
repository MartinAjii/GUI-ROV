import cv2
import threading
import time
from backend import config
from fastapi.responses import StreamingResponse

class CameraStream:
    def __init__(self, device, width, height, fps):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.latest_frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        cap = cv2.VideoCapture(self.device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        while self.running:
            ret, frame = cap.read()
            if ret:
                with self.lock:
                    self.latest_frame = frame
            else:
                time.sleep(0.1)
                
    def get_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None

    def generate_mjpeg(self):
        while self.running:
            frame = self.get_frame()
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(1.0 / self.fps)

cam1 = CameraStream(config.CAMERA1_DEVICE, config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS)
cam2 = CameraStream(config.CAMERA2_DEVICE, config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS)

def get_cam1_stream():
    return StreamingResponse(cam1.generate_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

def get_cam2_stream():
    return StreamingResponse(cam2.generate_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")
