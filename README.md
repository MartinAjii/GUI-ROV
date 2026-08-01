# ROV Control Dashboard — Veteran Leviathan

Dashboard kontrol untuk ROV / kapal selam robotik, dibuat dengan **HTML + CSS + JavaScript murni** (tanpa framework, tanpa build step) supaya mudah dijalankan langsung di laptop topside station maupun di-embed ke aplikasi lain (mis. Electron) kalau nanti dibutuhkan.

## Struktur proyek

```
rov-dashboard/
├── index.html              # Struktur halaman (header, kamera, panel QR/gripper/controller, telemetry bar)
├── css/
│   └── style.css           # Seluruh tampilan (tema navy gelap sesuai desain referensi)
├── js/
│   ├── config.js           # Pengaturan: URL WebSocket backend, device ID kamera, dsb.
│   ├── telemetry.js        # Koneksi WebSocket ke backend ROV, update depth/pitch/roll/yaw/battery/mission time
│   ├── camera-qr.js        # Menyalakan 2 feed kamera + scan QR code LIVE dengan jsQR
│   ├── gripper.js          # Logika tombol OPEN/CLOSED gripper
│   ├── controller.js       # Membaca Xbox controller / gamepad lewat Gamepad API browser
│   └── main.js             # Entry point, menyambungkan semua modul saat halaman dimuat
└── assets/
    └── logo-placeholder.svg  # Ganti dengan logo kampus/tim kalian
```

## Bagaimana bagian dinamis bekerja

- **Kamera (CAMERA BOTTOM / CAMERA WALL)**: memakai `navigator.mediaDevices.getUserMedia()`, jadi menampilkan video sungguhan dari kamera/USB capture card yang tersambung ke laptop/PC topside. Atur `CONFIG.camera.bottomDeviceId` / `wallDeviceId` di `js/config.js` kalau kalian punya lebih dari satu kamera dan perlu memilih yang mana untuk feed yang mana.
- **QR DETECTION**: setiap ~250 ms, frame dari feed CAMERA BOTTOM diambil dan diproses oleh library **jsQR** (CDN, tanpa perlu instalasi). Kalau QR code terbaca:
  - kotak **DECODED DATA** diisi teks hasil scan,
  - thumbnail **PREVIEW** di-crop otomatis dari area QR yang terdeteksi di frame video (jadi selalu menampilkan QR terakhir yang benar-benar terlihat kamera, bukan gambar statis),
  - **LAST DETECTION** diisi waktu saat itu.
- **GRIPPER**: tombol OPEN/CLOSED mengirim perintah ke backend lewat WebSocket (`Telemetry.send(...)`). Kalau backend ROV mengirim balik status gripper (misalnya digerakkan lewat controller fisik), UI otomatis ikut berubah lewat `Gripper.setState()`.
- **CONTROLLER**: memakai **Gamepad API** bawaan browser — begitu Xbox controller (USB/Bluetooth) tersambung ke komputer dan salah satu tombolnya ditekan sekali, browser akan mendeteksinya dan panel akan berubah menjadi `CONNECTED`, tombol yang ditekan akan menyala hijau secara real-time.
- **DEPTH / PITCH / ROLL / YAW / BATTERY / MISSION TIME**: diperbarui dari pesan JSON yang dikirim backend ROV lewat WebSocket. Kalau backend belum siap, dashboard otomatis memakai **mode simulasi** (data acak) supaya tampilan tetap bisa dicoba — atur lewat `CONFIG.useSimulationWhenOffline`.

## Menyambungkan ke backend ROV kalian sendiri

1. Buka `js/config.js`, isi `websocketUrl` dengan alamat WebSocket server di Raspberry Pi / topside PC kalian, misalnya:
   ```js
   websocketUrl: "ws://192.168.4.1:8765",
   ```
2. Backend kirim pesan JSON seperti ini setiap kali ada data baru:
   ```json
   { "type": "telemetry", "depth": 1.8, "pitch": 1.0, "roll": 1.8, "yaw": 44.5, "battery": 14.8, "connected": true }
   ```
3. Dashboard akan mengirim balik perintah gripper dan hasil scan QR ke backend dalam format:
   ```json
   { "type": "gripper_command", "state": "open" }
   { "type": "qr_detected", "data": "OBJECT:VALVE:SECTOR-C", "ts": 1735689900000 }
   ```
   Sesuaikan parsing di sisi backend (Python/Node/dll) dengan format ini.

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
