# ROV Control Dashboard — Veteran Leviathan

Dashboard kontrol untuk ROV / kapal selam robotik, dibuat dengan **HTML + CSS + JavaScript murni** (tanpa framework, tanpa build step) supaya mudah dijalankan langsung di laptop topside station maupun di-embed ke aplikasi lain (mis. Electron) kalau nanti dibutuhkan.

## Arsitektur lapangan (Raspberry Pi + Pixhawk)

```
Pixhawk --USB serial--> Raspberry Pi --mavlink_bridge.py--> WebSocket :8765 --\
Kamera BOTTOM/WALL --USB--> Raspberry Pi --camera_stream.py--> HTTP :5000    --+--> hAP lite (LAN) --> Laptop topside (dashboard ini)
```

Frontend (folder ini) jalan di **laptop topside**, dan berkomunikasi lewat
LAN (mikrotik hAP lite) ke backend Python yang jalan di **Raspberry Pi**
(folder `backend/`) — bukan lagi mengakses kamera langsung dari laptop.
Detail setup & testing backend ada di `backend/README_BACKEND.md`.

## Struktur proyek

```
rov-dashboard/
├── index.html              # Struktur halaman (header, kamera, panel QR/gripper/controller, telemetry bar)
├── css/
│   └── style.css           # Seluruh tampilan (tema navy gelap sesuai desain referensi)
├── js/
│   ├── config.js           # Pengaturan: URL WebSocket backend, mode kamera (network/local), dsb.
│   ├── telemetry.js        # Koneksi WebSocket ke backend ROV, update depth/pitch/roll/yaw/battery/mission time
│   ├── camera-qr.js        # Menyalakan 2 feed kamera (MJPEG dari Pi atau getUserMedia lokal) + scan QR code LIVE dengan jsQR
│   ├── gripper.js          # Logika tombol OPEN/CLOSED gripper
│   ├── controller.js       # Membaca Xbox controller / gamepad lewat Gamepad API browser
│   └── main.js             # Entry point, menyambungkan semua modul saat halaman dimuat
├── backend/                 # Jalan di Raspberry Pi: jembatan MAVLink<->WebSocket + server MJPEG kamera
│   ├── config.py
│   ├── mavlink_bridge.py
│   ├── camera_stream.py
│   ├── run_backend.py
│   ├── requirements.txt
│   └── README_BACKEND.md
└── assets/
    └── logo-placeholder.svg  # Ganti dengan logo kampus/tim kalian
```

## Bagaimana bagian dinamis bekerja

- **Kamera (CAMERA BOTTOM / CAMERA WALL)**: diatur lewat `CONFIG.camera.mode` di `js/config.js`.
  - `"network"` (default, sesuai setup lapangan kalian): video diambil lewat MJPEG stream dari `camera_stream.py` yang jalan di Raspberry Pi, lewat LAN (hAP lite). Elemen kamera otomatis ditampilkan sebagai `<img>`.
  - `"local"`: `navigator.mediaDevices.getUserMedia()`, untuk kamera/USB capture card yang tersambung langsung ke laptop topside (mode latihan/testing di meja tanpa Raspberry Pi). Atur `CONFIG.camera.bottomDeviceId` / `wallDeviceId`.
- **QR DETECTION**: setiap ~250 ms, frame dari feed CAMERA BOTTOM (baik `<img>` dari stream Pi maupun `<video>` lokal) diambil dan diproses oleh library **jsQR** (CDN, tanpa perlu instalasi). Kalau QR code terbaca:
  - kotak **DECODED DATA** diisi teks hasil scan,
  - thumbnail **PREVIEW** di-crop otomatis dari area QR yang terdeteksi di frame video (jadi selalu menampilkan QR terakhir yang benar-benar terlihat kamera, bukan gambar statis),
  - **LAST DETECTION** diisi waktu saat itu,
  - hasilnya juga dikirim ke backend Raspberry Pi lewat WebSocket dan dicatat ke `backend/qr_detections.csv`.
- **GRIPPER**: tombol OPEN/CLOSED mengirim perintah ke backend lewat WebSocket (`Telemetry.send(...)`). Backend meneruskannya sebagai perintah servo MAVLink ke Pixhawk (`backend/mavlink_bridge.py`). Kalau Pixhawk melaporkan posisi servo gripper (misal digerakkan lewat controller fisik), UI otomatis ikut berubah lewat `Gripper.setState()`.
- **CONTROLLER**: memakai **Gamepad API** bawaan browser — begitu Xbox controller (USB/Bluetooth) tersambung ke komputer dan salah satu tombolnya ditekan sekali, browser akan mendeteksinya dan panel akan berubah menjadi `CONNECTED`, tombol yang ditekan akan menyala hijau secara real-time.
- **DEPTH / PITCH / ROLL / YAW / BATTERY / MISSION TIME**: diperbarui dari pesan JSON yang dikirim `backend/mavlink_bridge.py` lewat WebSocket, hasil baca MAVLink dari Pixhawk (`ATTITUDE`, `GLOBAL_POSITION_INT`, `SYS_STATUS`). Kalau backend belum siap, dashboard otomatis memakai **mode simulasi** (data acak) supaya tampilan tetap bisa dicoba — atur lewat `CONFIG.useSimulationWhenOffline`.

## Menyambungkan ke Raspberry Pi + Pixhawk kalian

1. Ikuti `backend/README_BACKEND.md` untuk menjalankan `mavlink_bridge.py` dan `camera_stream.py` di Raspberry Pi (satu perintah: `python3 run_backend.py`).
2. Buka `js/config.js` di laptop topside, isi `websocketUrl`, `camera.bottomStreamUrl`, dan `camera.wallStreamUrl` dengan IP Raspberry Pi di jaringan hAP lite kalian, misalnya:
   ```js
   websocketUrl: "ws://192.168.88.10:8765",
   camera: {
     mode: "network",
     bottomStreamUrl: "http://192.168.88.10:5000/stream/bottom",
     wallStreamUrl: "http://192.168.88.10:5000/stream/wall",
   }
   ```
3. Format pesan JSON yang dikirim backend (sudah diimplementasikan di `mavlink_bridge.py`, tidak perlu diubah):
   ```json
   { "type": "telemetry", "depth": 1.8, "pitch": 1.0, "roll": 1.8, "yaw": 44.5, "battery": 14.8, "connected": true }
   ```
4. Dashboard mengirim balik perintah gripper dan hasil scan QR ke backend dalam format:
   ```json
   { "type": "gripper_command", "state": "open" }
   { "type": "qr_detected", "data": "OBJECT:VALVE:SECTOR-C", "ts": 1735689900000 }
   ```

## Langkah menjalankan (development / lomba)

Browser memblokir akses kamera (`getUserMedia`) kalau halaman dibuka langsung lewat `file://`, jadi harus dijalankan lewat server lokal — sangat mudah, tidak perlu instalasi berat.

### Opsi A — Python (paling simpel, biasanya sudah terpasang)
```bash
cd rov-dashboard
python3 -m http.server 8080
```
Lalu buka `http://localhost:8080` di browser (Chrome/Edge disarankan, dukungan Gamepad API paling stabil).

### Opsi B — Node.js
```bash
cd rov-dashboard
npx serve .
```
Buka URL yang muncul di terminal (biasanya `http://localhost:3000`).

### Opsi C — VS Code
Install ekstensi **Live Server**, klik kanan `index.html` → **Open with Live Server**.

### Setelah terbuka:
1. Browser akan meminta izin akses kamera — klik **Allow/Izinkan** (akan muncul 2x kalau feed BOTTOM dan WALL memakai kamera berbeda).
2. Sambungkan Xbox controller lewat USB/Bluetooth, tekan salah satu tombol supaya terdeteksi browser.
3. Arahkan QR code ke kamera yang dipakai untuk **CAMERA BOTTOM** — panel QR DETECTION akan otomatis terisi.
4. Ganti `assets/logo-placeholder.svg` dengan logo kampus/tim kalian (boleh format `.png`/`.svg`, tinggal ubah `src` di `index.html`).
5. Kalau sudah siap ke lapangan, isi `websocketUrl` di `js/config.js` supaya telemetry, baterai ROV, dan status gripper diambil dari perangkat sungguhan, bukan simulasi.

## Kompatibilitas
- Direkomendasikan Chrome/Edge terbaru (dukungan Gamepad API & getUserMedia paling lengkap).
- Untuk dipakai di lapangan lewat jaringan lokal (bukan localhost), kamera butuh koneksi **HTTPS** kecuali diakses lewat `localhost` — kalau topside PC dan laptop kontrol berbeda perangkat, pertimbangkan reverse proxy HTTPS sederhana (mis. `mkcert` + `http-server`) atau jalankan dashboard langsung di topside PC yang sama dengan kamera.
