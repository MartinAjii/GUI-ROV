/**
 * camera-qr.js
 * ---------------------------------------------------------------
 * 1) Menyalakan dua feed kamera (CAMERA BOTTOM & CAMERA WALL) lewat
 *    getUserMedia. Ganti CONFIG.camera.*DeviceId kalau kalian pakai
 *    capture card / kamera USB eksternal untuk ROV.
 * 2) Memindai QR code secara live dari feed CAMERA BOTTOM memakai
 *    library jsQR, lalu menampilkan hasilnya (bukan gambar statis)
 *    ke panel QR DETECTION: thumbnail preview + teks hasil decode.
 * ---------------------------------------------------------------
 */
const CameraQR = (() => {
  const videoBottom = document.getElementById("camBottom");
  const videoWall = document.getElementById("camWall");
  const scanCanvas = document.getElementById("camBottomCanvas");
  const scanCtx = scanCanvas.getContext("2d", { willReadFrequently: true });

  const previewCanvas = document.getElementById("qrPreviewCanvas");
  const previewCtx = previewCanvas.getContext("2d");

  let lastDecodedText = null;

  async function start() {
    await Promise.all([
      openFeed(videoBottom, CONFIG.camera.bottomDeviceId),
      openFeed(videoWall, CONFIG.camera.wallDeviceId),
    ]);
    startClocks();
    requestAnimationFrame(scanLoop);
  }

  async function openFeed(videoEl, deviceId) {
    try {
      const constraints = {
        video: deviceId ? { deviceId: { exact: deviceId } } : { facingMode: "environment" },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      videoEl.srcObject = stream;
    } catch (err) {
      console.warn(`Tidak bisa membuka kamera untuk ${videoEl.id}:`, err.message);
      // Feed tetap kosong (background gelap) sampai kamera tersedia,
      // dashboard sisanya tetap berfungsi.
    }
  }

  function startClocks() {
    setInterval(() => {
      const now = new Date().toLocaleTimeString("id-ID", { hour12: false });
      document.getElementById("camBottomClock").textContent = now;
      document.getElementById("camWallClock").textContent = now;
    }, 1000);
  }

  let lastScanTime = 0;
  function scanLoop(timestamp) {
    if (timestamp - lastScanTime >= CONFIG.qrScanIntervalMs) {
      lastScanTime = timestamp;
      tryDecodeFrame();
    }
    requestAnimationFrame(scanLoop);
  }

  function tryDecodeFrame() {
    if (videoBottom.readyState !== videoBottom.HAVE_ENOUGH_DATA) return;

    scanCanvas.width = videoBottom.videoWidth;
    scanCanvas.height = videoBottom.videoHeight;
    scanCtx.drawImage(videoBottom, 0, 0, scanCanvas.width, scanCanvas.height);

    const imageData = scanCtx.getImageData(0, 0, scanCanvas.width, scanCanvas.height);
    const result = jsQR(imageData.data, imageData.width, imageData.height, {
      inversionAttempts: "dontInvert",
    });

    const badge = document.getElementById("qrBadge");

    if (result && result.data) {
      badge.textContent = "DETECTED";
      badge.className = "badge badge-green";

      // Update thumbnail preview HANYA saat ada QR baru terdeteksi,
      // supaya gambar preview = QR terakhir yang berhasil discan
      // (dinamis, bukan file statis).
      if (result.data !== lastDecodedText) {
        lastDecodedText = result.data;
        drawPreviewFromCorners(imageData, result.location);
        document.getElementById("qrDecoded").textContent = result.data;
        document.getElementById("qrLastDetection").textContent =
          new Date().toLocaleTimeString("id-ID", { hour12: false });

        // Beri tahu modul lain (misalnya kirim ke backend ROV)
        Telemetry.send({ type: "qr_detected", data: result.data, ts: Date.now() });
      }
      pulseScanBar();
    } else {
      badge.textContent = "SCANNING";
      badge.className = "badge badge-idle";
    }
  }

  // Crop area QR dari frame video (pakai koordinat 4 sudut dari jsQR)
  // lalu gambar ke canvas preview kecil di panel QR DETECTION.
  function drawPreviewFromCorners(imageData, location) {
    const xs = [
      location.topLeftCorner.x, location.topRightCorner.x,
      location.bottomLeftCorner.x, location.bottomRightCorner.x,
    ];
    const ys = [
      location.topLeftCorner.y, location.topRightCorner.y,
      location.bottomLeftCorner.y, location.bottomRightCorner.y,
    ];
    const minX = Math.max(0, Math.min(...xs) - 10);
    const minY = Math.max(0, Math.min(...ys) - 10);
    const size = Math.max(...xs) - minX + 10;

    previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    previewCtx.drawImage(
      scanCanvas,
      minX, minY, size, size,
      0, 0, previewCanvas.width, previewCanvas.height
    );
  }

  function pulseScanBar() {
    const fill = document.getElementById("scanBarFill");
    fill.style.width = "100%";
    setTimeout(() => (fill.style.width = "0%"), 400);
  }

  return { start };
})();
