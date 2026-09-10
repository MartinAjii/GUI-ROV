# Tombol STOP / DISARM

Tombol merah ada tepat di bawah header dan tetap terlihat saat halaman digulir.
Satu klik meminta DISARM biasa ke Pixhawk melalui WebSocket → backend → forwarder → Pixhawk.
Perintah ini tidak memutus listrik baterai, ESC, Raspberry Pi, atau kamera, dan tidak menggantikan emergency stop fisik.

## Memasang revisi

Ekstrak arsip di folder terpisah. Untuk memperbarui instalasi Raspi yang sudah berjalan,
salin file berikut dari hasil ekstrak ke lokasi yang sama di folder GUI-ROV milikmu:

- index.html
- css/style.css
- js/emergency-stop.js (baru)
- js/telemetry.js
- js/main.js
- js/config.js
- backend/stop_control.py (baru)
- backend/mavlink_bridge.py
- backend/config.py

Jika konfigurasi lokalmu sudah berbeda dari ZIP yang dikirim, pertahankan alamat dan
pengaturan kamera lokal ketika menggabungkan file config. docker-compose.yml dan
mavlink_forwarder.py tidak berubah dalam revisi ini. Tidak perlu menyalin folder .git.

Dari folder GUI-ROV di Raspberry Pi, bangun ulang hanya backend:

```bash
docker compose up -d --build rov-backend
```

Buka GUI dari backend Raspberry Pi (misalnya http://192.168.0.1:8000), lalu tekan
Ctrl+F5 agar JavaScript baru dimuat. Membuka index.html lewat file:// atau server
statis laptop tidak menyediakan backend perintah DISARM.

## Membaca status

- ARMED: heartbeat terbaru melaporkan Pixhawk armed.
- MENUNGGU DISARM: permintaan sedang diproses. Belum ada konfirmasi disarm.
- DISARMED: heartbeat terbaru dari autopilot melaporkan disarmed. Ini bukan pengukuran putaran motor atau pemutusan listrik.
- Ditolak: autopilot menolak perintah normal. Kode ACK ditampilkan; pemeriksaan keselamatan tidak dilewati.
- Belum terkonfirmasi: gagal kirim, heartbeat hilang, atau batas waktu terlampaui. Jangan menganggap ROV sudah berhenti.
- STATUS TIDAK DIKETAHUI: tidak ada telemetry baru yang memadai. Tombol dinonaktifkan.

Klik STOP tidak membuka dialog konfirmasi tambahan. Tombol dinonaktifkan sementara
permintaan diproses supaya klik ganda tidak membanjiri jalur perintah. Backend mencoba
maksimal tiga pengiriman dalam batas tunggu lima detik, berhenti ketika ada ACK atau
heartbeat disarmed, dan tidak mengantrekan perintah untuk diputar ulang setelah koneksi pulih.
ACK diterima saja bukan bukti disarmed. Heartbeat yang sudah kedaluwarsa tidak ditampilkan
sebagai status disarmed saat ini. Jika aplikasi lain kembali meng-arm ROV, GUI menampilkan
ARMED kembali. Fitur ini tidak mengunci re-arm dari Mission Planner atau aplikasi lain.

Tidak ada fungsi ARM, force-disarm, atau perubahan parameter failsafe yang ditambahkan.
Simulasi otomatis ketika offline dinonaktifkan pada konfigurasi default agar telemetry
acak tidak tampil ketika sedang menangani penghentian. Tombol tetap tidak bisa memakai
data simulasi, sekalipun opsi simulasi diaktifkan lagi untuk pengembangan.

## Detail untuk pengembang

Backend memakai socket telemetry yang sudah ada, udpin:127.0.0.1:14551. Pymavlink
membalas ke endpoint UDP forwarder yang mengirim telemetry, dan forwarder meneruskan
balasan ke serial. Tidak ada pembaca serial kedua atau listener baru pada 14550.
Target dipilih dari heartbeat ArduPilot tipe SUBMARINE, component autopilot 1,
dan dipertahankan untuk koneksi itu. Heartbeat GCS/kamera tidak menjadi target.

COMMAND_LONG memakai MAV_CMD_COMPONENT_ARM_DISARM, param1=0 dan param2=0.
Source system default 255, component 191. STOP_SOURCE_SYSTEM dapat disesuaikan
oleh pengelola jika SYSID_MYGCS menggunakan ID lain; jangan menonaktifkan pemeriksaan
keselamatan untuk mengatasi perintah ditolak. Backend tidak membuat heartbeat GCS
baru yang dapat menyamarkan hilangnya aplikasi kontrol permukaan.

GUI mengirim {"type":"command","command":"disarm","id":"ID-unik"}.
Backend membalas command_result serta menyiarkan connected, armed, stop_available,
dan stop melalui telemetry. Perintah lain tidak diteruskan oleh handler ini.
Layanan masih mengikuti model jaringan lokal proyek asal; belum ditambahkan autentikasi.

## Validasi revisi

Pengujian tanpa perangkat:

```bash
python -m unittest discover -s tests -p test_stop_control.py -v
node tests/test_stop_ui.cjs
```

13 tes backend dan tes status UI lolos dengan transport/heartbeat tiruan.
Sintaks Python dan JavaScript telah diperiksa. Tidak ada pengujian pada Pixhawk,
ESC, atau thruster fisik, maupun validasi visual browser dalam lingkungan ini.
Minta pembimbing/teknisi memverifikasi jalur DISARM dengan daya penggerak diisolasi
sebelum mengandalkan fitur ini pada ROV. Emergency stop fisik tetap diperlukan.

Referensi protokol:
- https://ardupilot.org/dev/docs/mavlink-arming-and-disarming.html
- https://mavlink.io/en/services/command.html
