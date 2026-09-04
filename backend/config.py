import os

SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/px")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "115200"))
GCS_UDP_HOST = os.getenv("GCS_UDP_HOST", "192.168.1.100")
GCS_UDP_PORT = int(os.getenv("GCS_UDP_PORT", "14550"))
LOCAL_TELEMETRY_UDP_PORT = int(os.getenv("LOCAL_TELEMETRY_UDP_PORT", "14551"))

CAMERA1_DEVICE = os.getenv("CAMERA1_DEVICE", "/dev/cam_cheap")
CAMERA2_DEVICE = os.getenv("CAMERA2_DEVICE", "/dev/cam_logitech")
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))
MJPEG_QUALITY = int(os.getenv("MJPEG_QUALITY", "65"))

GCS_VIDEO_ENABLED = os.getenv("GCS_VIDEO_ENABLED", "true").lower() == "true"
GCS_VIDEO_IP = os.getenv("GCS_VIDEO_IP", "192.168.1.100")
GCS_VIDEO_PORT = int(os.getenv("GCS_VIDEO_PORT", "5600"))
GCS_VIDEO_BITRATE = os.getenv("GCS_VIDEO_BITRATE", "2M")

GRIPPER_SERVO_CHANNEL = int(os.getenv("GRIPPER_SERVO_CHANNEL", "9"))
GRIPPER_PWM_OPEN = int(os.getenv("GRIPPER_PWM_OPEN", "1900"))
GRIPPER_PWM_CLOSED = int(os.getenv("GRIPPER_PWM_CLOSED", "1100"))

DEPTH_SOURCE = os.getenv("DEPTH_SOURCE", "pressure") # "pressure" or "rangefinder"
TELEMETRY_HZ = int(os.getenv("TELEMETRY_HZ", "10"))
HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))
