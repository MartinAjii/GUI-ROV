"""
config.py
---------------------------------------------------------------
Konfigurasi backend yang berjalan di Raspberry Pi.
Sesuaikan nilai-nilai di sini dengan setup ROV kalian.
---------------------------------------------------------------
"""

# ============================================================
# PIXHAWK (MAVLink)
# ============================================================
# Port serial Pixhawk saat disambung USB ke Raspberry Pi.
# Cek dengan `ls /dev/serial/by-id/` atau `dmesg | grep tty` setelah dicolok.
# Paling aman pakai path /dev/serial/by-id/... karena tidak berubah-ubah
# seperti /dev/ttyACM0 yang bisa bergeser urutannya.
MAVLINK_CONNECTION = "/dev/ttyACM0"
MAVLINK_BAUD = 115200

# Kalau Pixhawk kalian jalan di firmware ArduSub (umum untuk ROV/kapal
# selam), depth diambil dari GLOBAL_POSITION_INT.relative_alt.
# Kalau firmware kalian beda dan tidak mengirim pesan ini, ubah
# DEPTH_SOURCE ke "baro" untuk pakai SCALED_PRESSURE (butuh kalibrasi
# tekanan air sendiri -> lihat catatan di mavlink_bridge.py).
DEPTH_SOURCE = "global_position_int"  # "global_position_int" | "baro"

# ============================================================
# WEBSOCKET (ke dashboard di laptop topside)
# ============================================================
WS_HOST = "0.0.0.0"   # dengar di semua interface LAN
WS_PORT = 8765
TELEMETRY_SEND_HZ = 5  # seberapa sering kirim update ke dashboard (per detik)

# ============================================================
# GRIPPER
# ============================================================
# Default: gripper digerakkan lewat servo output Pixhawk (MAV_CMD_DO_SET_SERVO),
# karena Pixhawk sudah tersambung by USB serial -> tidak perlu kabel/relay
# tambahan di GPIO Raspberry Pi. Kalau ternyata gripper kalian dikendalikan
# lewat relay/motor driver terpisah di Raspberry Pi, ubah GRIPPER_MODE ke
# "gpio" dan sesuaikan pin di bawah.
GRIPPER_MODE = "servo"  # "servo" | "gpio"

# --- mode "servo" ---
GRIPPER_SERVO_CHANNEL = 9      # channel servo/AUX di Pixhawk untuk gripper
GRIPPER_OPEN_PWM = 1900
GRIPPER_CLOSED_PWM = 1100

# --- mode "gpio" (kalau dipakai) ---
GRIPPER_GPIO_PIN = 17
GRIPPER_GPIO_ACTIVE_HIGH = True

# ============================================================
# KAMERA (MJPEG streaming lewat LAN)
# ============================================================
CAMERA_HTTP_HOST = "0.0.0.0"
CAMERA_HTTP_PORT = 5000

# Index /dev/videoN masing-masing kamera. Cek dengan `v4l2-ctl --list-devices`.
CAMERA_BOTTOM_INDEX = 0
CAMERA_WALL_INDEX = 2

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 20
CAMERA_JPEG_QUALITY = 80  # 1-100, makin rendah makin ringan di LAN

# ============================================================
# LOG QR
# ============================================================
QR_LOG_FILE = "qr_detections.csv"
