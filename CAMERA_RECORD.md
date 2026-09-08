# Rekam kamera langsung ke laptop

Ekstrak ZIP ini di **laptop**. Program `laptop_recorder` menerima stream kamera
dari Raspberry Pi, menampilkan GUI, dan menulis video bertahap ke disk laptop.
Rekaman tidak disimpan di microSD Pi dan tidak dikumpulkan seluruhnya di RAM
browser. Dua kamera berbagi masing-masing satu koneksi stream untuk preview
dan perekaman. Telemetry serta pesan controller diteruskan ke backend Pi.

## 1. Siapkan Raspberry Pi

Backend GUI-ROV tetap berjalan seperti biasa di port 8000. Tidak perlu memasang
program perekam laptop di Pi atau mengubah pemetaan perangkat Pixhawk/kamera.

Salin `backend/camera_stream.py` dari ZIP ini ke proyek di Pi lalu rebuild
service backend. Perubahan ini membuat stream berhenti mengirim gambar lama
ketika kamera tidak menghasilkan frame baru, sehingga perekam laptop dapat
mendeteksi kamera yang terputus.

Jika sudah memasang versi rekam-ke-Pi yang sebelumnya diberikan, salin juga
`backend/run_backend.py` dari ZIP ini untuk menonaktifkan API perekaman Pi.
Hentikan rekaman lama sebelum rebuild. Video lama di Pi tidak dihapus otomatis.

Jalankan dari folder proyek di Pi:

```bash
docker compose up -d --build --no-deps rov-backend
```

Pertahankan `docker-compose.yml` milikmu yang pemetaan perangkatnya sudah benar.
ZIP ini tidak membutuhkan volume `recordings` pada service Pi. Kalau volume itu
sudah ditambahkan sebelumnya, boleh dibiarkan; perekam baru tidak menulis ke sana.

Pastikan alamat backend Pi dapat dibuka dari laptop. Pada contoh berikut,
**192.168.0.1 hanya contoh**: ganti dengan IP Raspberry Pi kamu, bukan IP laptop.

## 2. Pasang di laptop — Windows (PowerShell)

Gunakan Python 3.10–3.13. Buka PowerShell di folder `GUI-ROV` hasil ekstrak:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r laptop_recorder/requirements.txt
.\.venv\Scripts\python.exe -m laptop_recorder.app --pi http://192.168.0.1:8000
```

Tidak perlu aktivasi virtual environment atau mengubah execution policy.
Instalasi dependensi memerlukan internet sekali. Untuk pemakaian berikutnya,
cukup jalankan perintah terakhir dari folder yang sama.

## 3. Alternatif — Fedora/Linux

Buka terminal di folder `GUI-ROV` hasil ekstrak:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r laptop_recorder/requirements.txt
.venv/bin/python -m laptop_recorder.app --pi http://192.168.0.1:8000
```

Untuk pemakaian berikutnya cukup jalankan perintah terakhir. Jika Python sistem
belum didukung paket OpenCV yang tersedia, gunakan Python 3.10–3.13.

## 4. Buka GUI dan rekam

Buka **http://127.0.0.1:8080** di browser laptop. Untuk fitur ini, jangan membuka
HTML secara langsung, server `python -m http.server`, atau GUI di alamat Pi.
Biarkan terminal perekam tetap berjalan. `CONFIG.camera.mode` tetap `network`;
URL kamera dan WebSocket bawaan sudah diarahkan lewat program laptop.

1. Tunggu gambar kamera dan telemetry tersambung.
2. Klik **Mulai rekam** pada CAMERA BOTTOM atau CAMERA WALL.
3. Indikator **REC + durasi** muncul. Kedua kamera bisa direkam bersamaan.
4. Klik **Stop rekam** untuk menyelesaikan video agar siap dibuka.
5. Buka folder video yang tertulis di panel. **Tidak perlu mengunduh**: file
   sudah berada di laptop. Daftar rekaman menyediakan unduhan salinan bila perlu.

Folder default: `<folder pengguna>/Videos/GUI-ROV`, misalnya:
- Windows: `C:\Users\NamaKamu\Videos\GUI-ROV`
- Linux: `/home/namakamu/Videos/GUI-ROV`

Nama file menggunakan kamera, waktu UTC, dan ID unik. Format AVI/MJPEG tanpa
audio, crosshair, QR overlay, atau telemetry. Folder dibuat saat rekaman pertama.

Untuk memilih folder lain atau disk eksternal di Windows:

```powershell
.\.venv\Scripts\python.exe -m laptop_recorder.app --pi http://192.168.0.1:8000 --output "D:\Rekaman-ROV"
```

Di Fedora/Linux:

```bash
.venv/bin/python -m laptop_recorder.app --pi http://192.168.0.1:8000 --output "$HOME/Videos/Rekaman-ROV"
```

Jika port 8080 sudah dipakai, tambahkan `--port 8081` dan buka
`http://127.0.0.1:8081`. Untuk FPS lain, gunakan `--fps 10` (1–30); sesuaikan
dengan `CAMERA_FPS` di Pi, default 15.

## Perilaku saat terputus atau berhenti

- Refresh/menutup tab tidak menghentikan perekaman selama program laptop aktif.
- Menutup program menghentikan perekaman. Stop di GUI dahulu, lalu tekan Ctrl+C
  di terminal dan tunggu program selesai. Jangan paksa tutup saat menyelesaikan video.
- Putus jaringan/kamera lebih dari sekitar 2 detik menghentikan rekaman dan
  menyelesaikan file. Setelah tersambung lagi, klik Mulai rekam untuk file baru;
  rekaman tidak otomatis dimulai kembali. Deteksi kabel kamera memerlukan update
  `camera_stream.py` di Pi seperti langkah 1.
- Sisakan daya dan cegah laptop masuk sleep selama merekam.
- File lama tidak dihapus otomatis. Perekaman ditolak/dihentikan bila disk laptop
  tersisa kurang dari 512 MB. File MJPEG tetap relatif besar; pindahkan atau hapus
  rekaman selesai yang tidak diperlukan.
- Satu program perekam per port/output. Layanan hanya mendengarkan di localhost.
- Menggunakan GUI laptop membuat koneksi telemetry/controller melewati program
  laptop. Keluar dari program juga memutus koneksi tersebut.

## Pengujian

```bash
python -m unittest discover -s tests -p 'test_*record*.py' -v
```

Pengujian mencakup AVI yang dapat dibaca kembali, dua kamera, penolakan disk
penuh, kamera terputus, parser MJPEG terfragmentasi, stream HTTP sungguhan dari
server sintetis ke file lokal, shutdown, serta penerusan WebSocket dua arah.
Performa, kamera fisik, dan keseluruhan kendali ROV perlu diverifikasi di
perangkat sebenarnya. Kinerja encoding/disk yang tidak mencukupi dapat membuat
FPS aktual rendah dan durasi playback berbeda dari durasi dinding.
