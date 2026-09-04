import cv2
import threading
import time
import subprocess
import logging
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
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        if fourcc_str != 'MJPG':
            logging.warning(f"Warning: {self.device} failed to set MJPG, got {fourcc_str}")
        
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
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, config.MJPEG_QUALITY])
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

class GCSVideoEncoder:
    def __init__(self, camera_stream, gcs_ip, gcs_port, width, height, fps, bitrate):
        self.camera_stream = camera_stream
        self.gcs_ip = gcs_ip
        self.gcs_port = gcs_port
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.running = False
        self.thread = None
        self.proc = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._encode_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
        if self.thread:
            self.thread.join()

    def _start_ffmpeg(self):
        try:
            output = subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.STDOUT).decode()
            if "h264_v4l2m2m" in output:
                encoder_opts = ["-c:v", "h264_v4l2m2m", "-b:v", self.bitrate]
            else:
                logging.warning("Hardware encoder h264_v4l2m2m not found, falling back to libx264")
                encoder_opts = ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-b:v", self.bitrate]
        except Exception as e:
            logging.warning(f"Error checking ffmpeg encoders: {e}, falling back to libx264")
            encoder_opts = ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-b:v", self.bitrate]

        cmd = [
            "ffmpeg",
            "-y", # Overwrite output if needed
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}", "-r", str(self.fps),
            "-i", "pipe:0",
            *encoder_opts,
            "-f", "mpegts", f"udp://{self.gcs_ip}:{self.gcs_port}",
        ]
        return subprocess.Popen(cmd, stdin=subprocess.PIPE)

    def _encode_loop(self):
        while self.running:
            if self.proc is None or self.proc.poll() is not None:
                if self.proc is not None:
                    logging.warning("ffmpeg process died, restarting...")
                self.proc = self._start_ffmpeg()
            
            frame = self.camera_stream.get_frame()
            if frame is not None:
                try:
                    self.proc.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    pass
            
            time.sleep(1.0 / self.fps)

gcs_encoder = None
def start_gcs_encoder_if_enabled():
    global gcs_encoder
    if config.GCS_VIDEO_ENABLED:
        gcs_encoder = GCSVideoEncoder(cam2, config.GCS_VIDEO_IP, config.GCS_VIDEO_PORT, config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS, config.GCS_VIDEO_BITRATE)
        gcs_encoder.start()

def stop_gcs_encoder():
    if gcs_encoder:
        gcs_encoder.stop()
