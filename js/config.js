/**
 * config.js
 * ---------------------------------------------------------------
 * Semua nilai yang berubah-ubah tergantung ROV/kapal selam kalian
 * dikumpulkan di sini, supaya file lain tidak perlu diutak-atik.
 * ---------------------------------------------------------------
 */
const CONFIG = {
  // Nama tim & nama ROV yang tampil di header. Bisa juga di-override
  // lewat query string: index.html?team=Nama%20Tim
  teamName: "Veteran Leviathan",

  // Alamat WebSocket backend ROV (mavlink_bridge.py) yang jalan di
  // Raspberry Pi. Ganti <IP-RASPBERRY-PI> dengan IP Pi di jaringan
  // hAP lite kalian, contoh: "ws://192.168.88.10:8765"
  websocketUrl: `ws://${window.location.host}/ws/telemetry`,

  // Reconnect otomatis kalau koneksi WebSocket putus
  wsReconnectDelayMs: 3000,

  camera: {
    // "network" = ambil video lewat MJPEG dari Raspberry Pi lewat LAN
    //             (setup lapangan kalian: laptop <-> hAP lite <-> Raspberry Pi).
    // "local"   = getUserMedia, kamera/capture card tersambung langsung
    //             ke laptop yang menjalankan browser (mode testing di meja).
    mode: "network",

    // --- dipakai kalau mode = "network" ---
    // Harus IP/hostname yang sama dengan MAVLINK websocket di atas
    // (satu Raspberry Pi yang sama), port beda karena servernya beda proses.
    bottomStreamUrl: "/video/cam1",
    wallStreamUrl: "/video/cam2",
    // Kalau feed putus (kabel LAN goyang dsb.), coba sambung ulang tiap sekian ms.
    streamReconnectDelayMs: 2000,

    // --- dipakai kalau mode = "local" ---
    // device ID kamera untuk masing-masing feed. Kosongkan untuk memakai
    // kamera default browser. Ambil daftar ID lewat:
    // navigator.mediaDevices.enumerateDevices()
    bottomDeviceId: "",
    wallDeviceId: "",
  },

  // Interval pemindaian QR (ms) dari feed CAMERA BOTTOM
  qrScanIntervalMs: 150,

  // Kalau true, dan tidak ada backend WebSocket, panel telemetry/gripper/
  // controller akan diisi data acak supaya tampilan bisa langsung dicoba.
  useSimulationWhenOffline: true,
};
