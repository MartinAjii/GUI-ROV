# Backend ROV — Raspberry Pi

Menjembatani **Pixhawk** (MAVLink lewat USB serial) dan **kamera** ke
dashboard web di laptop topside, lewat jaringan **hAP lite** (LAN).

```
Pixhawk --USB--> Raspberry Pi --mavlink_bridge.py--> WebSocket :8765 --\
Kamera BOTTOM/WALL --USB--> Raspberry Pi --camera_stream.py--> HTTP :5000 --+--> hAP lite (LAN) --> Laptop topside (dashboard browser)
```

## 1. Instalasi di Raspberry Pi

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv v4l-utils

cd rov-dashboard/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Cek dulu satu-satu sebelum digabung

### a) Pixhawk lewat PuTTY / terminal
Pastikan device muncul:
```bash
ls /dev/serial/by-id/
# atau
dmesg | grep -i tty
```
Kalau kalian sudah pernah cek koneksi lewat Mission Planner dan attitude/depth-nya normal, berarti port & baudrate yang dipakai di sana (biasanya 115200) itulah yang harus diisi di `config.py` (`MAVLINK_CONNECTION`, `MAVLINK_BAUD`). **Jangan buka Mission Planner dan `mavlink_bridge.py` bersamaan ke port yang sama** — serial port cuma bisa dipakai satu program dalam satu waktu.

### b) Kamera
```bash
v4l2-ctl --list-devices
```
Catat index `/dev/videoN` untuk kamera BOTTOM dan WALL, isi ke `CAMERA_BOTTOM_INDEX` / `CAMERA_WALL_INDEX` di `config.py`.

## 3. Jalankan backend

```bash
python3 run_backend.py
```

Kalian akan lihat log seperti:
```
[CAM] Streaming di http://0.0.0.0:5000/stream/bottom
[CAM] Streaming di http://0.0.0.0:5000/stream/wall
[MAVLink] Menyambung ke /dev/ttyACM0 @ 115200...
[MAVLink] Heartbeat diterima, Pixhawk terhubung.
[WS] Server WebSocket jalan di ws://0.0.0.0:8765
```

## 4. Cari IP Raspberry Pi di jaringan hAP lite

```bash
hostname -I
```

Pakai IP itu di `js/config.js` pada laptop topside:
```js
websocketUrl: "ws://192.168.88.10:8765",
camera: {
  mode: "network",
  bottomStreamUrl: "http://192.168.88.10:5000/stream/bottom",
  wallStreamUrl: "http://192.168.88.10:5000/stream/wall",
}
```

## 5. Tes cepat tanpa buka dashboard dulu

- Kamera: buka `http://<ip-pi>:5000/stream/bottom` langsung di browser laptop — harus muncul video jalan.
- WebSocket: dari laptop (Chrome DevTools console) atau `wscat`:
  ```bash
  npx wscat -c ws://<ip-pi>:8765
  ```
  Harus muncul pesan JSON telemetry setiap beberapa ratus ms.

## 6. Kalibrasi gripper

Default: gripper pakai servo output Pixhawk channel **9**, PWM 1900=open /
1100=closed (`config.py`). Setelah `mavlink_bridge.py` jalan, klik tombol
OPEN/CLOSED di dashboard sambil lihat gripper fisiknya — kalau arahnya
kebalik, tukar nilai `GRIPPER_OPEN_PWM` dan `GRIPPER_CLOSED_PWM`. Kalau
channel servo-nya bukan 9, ubah `GRIPPER_SERVO_CHANNEL` sesuai output
mapping di Mission Planner (`Full Parameter List` → cari `SERVOx_FUNCTION`
yang di-set ke Gripper/RCPassThru).

## 7. QR code

Deteksi QR sepenuhnya jalan di **browser** (jsQR, di `js/camera-qr.js`) —
backend cuma menerima hasilnya lewat pesan `qr_detected` dan mencatatnya
ke `qr_detections.csv` di folder ini untuk dokumentasi/log misi. Supaya QR
terbaca jelas, arahkan QR ke kamera BOTTOM (bukan WALL) — itu satu-satunya
feed yang dipindai.

## 8. Jalankan otomatis saat Raspberry Pi boot (opsional)

```bash
sudo tee /etc/systemd/system/rov-backend.service > /dev/null <<'EOF'
[Unit]
Description=ROV Backend (MAVLink bridge + camera stream)
After=network.target

[Service]
WorkingDirectory=/home/pi/rov-dashboard/backend
ExecStart=/home/pi/rov-dashboard/backend/venv/bin/python3 run_backend.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now rov-backend
sudo journalctl -u rov-backend -f   # lihat log
```

Sesuaikan `WorkingDirectory` dan `ExecStart` dengan lokasi folder kalian
yang sebenarnya di Raspberry Pi.
