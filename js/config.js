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

  // Alamat WebSocket backend ROV kalian (Raspberry Pi / topside PC).
  // Kirim JSON dengan format lihat di telemetry.js -> handleTelemetryMessage()
  // Kosongkan ("") kalau belum ada backend -> dashboard akan pakai data simulasi.
  websocketUrl: "", // contoh: "ws://192.168.4.1:8765"

  // Reconnect otomatis kalau koneksi WebSocket putus
  wsReconnectDelayMs: 3000,

  // device ID kamera untuk masing-masing feed. Kosongkan untuk memakai
  // kamera default browser. Ambil daftar ID lewat:
  // navigator.mediaDevices.enumerateDevices()
  camera: {
    bottomDeviceId: "",   // contoh: "a1b2c3..."
    wallDeviceId: "",     // contoh: "d4e5f6..."
  },

  // Interval pemindaian QR (ms) dari feed CAMERA BOTTOM
  qrScanIntervalMs: 250,

  // Kalau true, dan tidak ada backend WebSocket, panel telemetry/gripper/
  // controller akan diisi data acak supaya tampilan bisa langsung dicoba.
  useSimulationWhenOffline: true,
};
