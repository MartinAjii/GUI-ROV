/**
 * camera-qr.js
 * ---------------------------------------------------------------
 * Menyalakan feed CAMERA BOTTOM & CAMERA WALL, lalu memindai QR
 * code secara live dari feed CAMERA BOTTOM memakai jsQR.
 *
 * Dua mode (diatur lewat CONFIG.camera.mode):
 *  - "network": video diambil lewat MJPEG stream dari Raspberry Pi
 *    (setup lapangan: laptop <-> hAP lite <-> Raspberry Pi + kamera).
 *    Elemen <video> di index.html otomatis diganti jadi <img> di sini,
 *    karena browser menonton MJPEG lewat tag <img>, bukan <video>.
 *  - "local": getUserMedia, kamera eksternal tersambung langsung ke
 *    laptop yang menjalankan browser (mode testing/latihan di meja).
 *
 * Pemindaian QR (jsQR) bekerja sama persis di kedua mode, karena
 * canvas.drawImage() menerima elemen <video> maupun <img>.
 * ---------------------------------------------------------------
 */

const CameraQR = (() => {
  let videoBottom = document.getElementById("camBottom");
  let videoWall = document.getElementById("camWall");

  const scanCanvas = document.getElementById("camBottomCanvas");
  const scanCtx = scanCanvas.getContext("2d", {
    willReadFrequently: true,
  });

  let lastDecodedText = null;

  const activeStreams = new Map();

  /*
   * Nama-nama yang biasanya digunakan oleh webcam internal laptop
   * (dipakai hanya di mode "local" supaya webcam bawaan laptop tidak
   * otomatis kepakai untuk feed ROV).
   */
  const INTERNAL_CAMERA_PATTERN =
    /integrated|built[ -]?in|facetime|truevision|wide vision|easycamera|front camera|user facing|surface.*camera|ir camera/i;

  async function start() {
    if (CONFIG.camera.mode === "network") {
      videoBottom = switchToImgElement(videoBottom);
      videoWall = switchToImgElement(videoWall);

      showNoImage(videoBottom);
      showNoImage(videoWall);

      startNetworkStream(videoBottom, CONFIG.camera.bottomStreamUrl);
      startNetworkStream(videoWall, CONFIG.camera.wallStreamUrl);
    } else {
      /*
       * Mode "local": jangan langsung menampilkan kamera apa pun
       * sampai kamera eksternal yang dikonfigurasi ditemukan.
       */
      showNoImage(videoBottom);
      showNoImage(videoWall);

      await connectExternalCameras();

      /*
       * Jika kamera ROV / capture card dicolok atau dilepas,
       * lakukan deteksi ulang tanpa perlu refresh halaman.
       */
      if (navigator.mediaDevices?.addEventListener) {
        navigator.mediaDevices.addEventListener(
          "devicechange",
          connectExternalCameras
        );
      }
    }

    startClocks();

    requestAnimationFrame(scanLoop);
  }

  /*
   * ============================================================
   * MODE "network": MJPEG dari Raspberry Pi lewat <img>
   * ============================================================
   */

  function switchToImgElement(el) {
    if (el.tagName === "IMG") return el;
    const img = document.createElement("img");
    img.id = el.id;
    img.className = el.className;
    el.replaceWith(img);
    return img;
  }

  function startNetworkStream(imgEl, url) {
    if (!url || url.includes("<IP-RASPBERRY-PI>")) {
      console.warn(
        `CONFIG.camera untuk ${imgEl.id} belum diisi IP Raspberry Pi yang benar (js/config.js).`
      );
      disconnectFeed(imgEl);
      return;
    }

    const connect = () => {
      imgEl.onload = () => {
        hideNoImage(imgEl);
        setCameraStatus(imgEl, true);
      };
      imgEl.onerror = () => {
        setCameraStatus(imgEl, false);
        showNoImage(imgEl);
        setTimeout(
          connect,
          CONFIG.camera.streamReconnectDelayMs || 2000
        );
      };
      // Cache-bust supaya browser selalu buka koneksi MJPEG baru,
      // bukan memakai gambar statis yang ke-cache.
      imgEl.src = `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
    };

    connect();
  }

  /*
   * ============================================================
   * MODE "local": DETEKSI KAMERA (getUserMedia)
   * ============================================================
   */

  async function connectExternalCameras() {
    if (
      !navigator.mediaDevices?.enumerateDevices ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      disconnectFeed(videoBottom);
      disconnectFeed(videoWall);
      return;
    }

    try {
      const devices = await navigator.mediaDevices.enumerateDevices();

      const videoInputs = devices.filter(
        (device) => device.kind === "videoinput"
      );

      console.log("=== DAFTAR KAMERA ===");
      videoInputs.forEach((device, index) => {
        console.log(`${index + 1}. ${device.label || "Unknown camera"}`);
        console.log(`Device ID: ${device.deviceId}`);
      });

      /*
       * Kamera hanya boleh digunakan kalau device ID sudah dimasukkan
       * ke CONFIG. Tidak ada auto fallback ke webcam laptop.
       */
      const bottomDevice = CONFIG.camera.bottomDeviceId
        ? videoInputs.find(
            (device) => device.deviceId === CONFIG.camera.bottomDeviceId
          )
        : null;

      const wallDevice = CONFIG.camera.wallDeviceId
        ? videoInputs.find(
            (device) => device.deviceId === CONFIG.camera.wallDeviceId
          )
        : null;

      if (bottomDevice) {
        await openFeed(videoBottom, bottomDevice.deviceId);
      } else {
        disconnectFeed(videoBottom);
      }

      if (wallDevice) {
        await openFeed(videoWall, wallDevice.deviceId);
      } else {
        disconnectFeed(videoWall);
      }
    } catch (error) {
      console.error("Camera detection error:", error);
      disconnectFeed(videoBottom);
      disconnectFeed(videoWall);
    }
  }

  async function openFeed(videoEl, deviceId) {
    try {
      stopStream(videoEl);

      if (!deviceId) {
        disconnectFeed(videoEl);
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: { exact: deviceId } },
        audio: false,
      });

      videoEl.srcObject = stream;
      activeStreams.set(videoEl.id, stream);

      await videoEl.play();

      hideNoImage(videoEl);
      setCameraStatus(videoEl, true);
    } catch (error) {
      console.error(`Camera ${videoEl.id} gagal dibuka:`, error);
      disconnectFeed(videoEl);
    }
  }

  /*
   * ============================================================
   * KAMERA TERPUTUS (dipakai kedua mode)
   * ============================================================
   */

  function disconnectFeed(el) {
    stopStream(el);
    if (el.tagName === "VIDEO") el.srcObject = null;
    else el.removeAttribute("src");

    showNoImage(el);
    setCameraStatus(el, false);
  }

  function stopStream(el) {
    if (el.tagName !== "VIDEO") return;
    const stream = activeStreams.get(el.id) || el.srcObject;
    if (stream?.getTracks) {
      stream.getTracks().forEach((track) => track.stop());
    }
    activeStreams.delete(el.id);
  }

  /*
   * ============================================================
   * TULISAN "NO IMAGE CONNECTED"
   * ============================================================
   */

  function getNoImageOverlay(el) {
    const cameraBody = el.closest(".camera-body");
    if (!cameraBody) return null;

    let overlay = cameraBody.querySelector(".camera-no-image");

    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "camera-no-image";
      overlay.textContent = "NO IMAGE CONNECTED";

      Object.assign(overlay.style, {
        position: "absolute",
        inset: "0",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#050b16",
        color: "rgba(255,255,255,0.55)",
        fontFamily: "var(--font-mono)",
        fontSize: "13px",
        fontWeight: "700",
        letterSpacing: "1.4px",
        zIndex: "10",
        pointerEvents: "none",
      });

      cameraBody.appendChild(overlay);
    }

    return overlay;
  }

  function showNoImage(el) {
    const overlay = getNoImageOverlay(el);
    if (overlay) overlay.style.display = "flex";
  }

  function hideNoImage(el) {
    const overlay = getNoImageOverlay(el);
    if (overlay) overlay.style.display = "none";
  }

  /*
   * ============================================================
   * STATUS LIVE / NO SIGNAL
   * ============================================================
   */

  function setCameraStatus(el, isLive) {
    const panel = el.closest(".camera-panel");
    const badge = panel?.querySelector(".panel-head .badge");
    if (!badge) return;

    if (isLive) {
      badge.className = "badge badge-live";
      badge.innerHTML = '<i class="dot dot-red pulse"></i>LIVE';
    } else {
      badge.className = "badge badge-idle";
      badge.textContent = "NO SIGNAL";
    }
  }

  /*
   * ============================================================
   * CLOCK CAMERA
   * ============================================================
   */

  function startClocks() {
    setInterval(() => {
      const now = new Date().toLocaleTimeString("id-ID", { hour12: false });
      const bottomClock = document.getElementById("camBottomClock");
      const wallClock = document.getElementById("camWallClock");
      if (bottomClock) bottomClock.textContent = now;
      if (wallClock) wallClock.textContent = now;
    }, 1000);
  }

  /*
   * ============================================================
   * QR SCANNER (bekerja untuk <video> maupun <img>)
   * ============================================================
   */

  let lastScanTime = 0;
  let lastDetectionTime = 0;

  function scanLoop(timestamp) {
    if (timestamp - lastScanTime >= CONFIG.qrScanIntervalMs) {
      lastScanTime = timestamp;
      tryDecodeFrame();
    }
    requestAnimationFrame(scanLoop);
  }

  function getFrameSize(el) {
    if (el.tagName === "VIDEO") {
      return { w: el.videoWidth, h: el.videoHeight };
    }
    return { w: el.naturalWidth, h: el.naturalHeight };
  }

  function isFrameReady(el) {
    if (el.tagName === "VIDEO") {
      return !!el.srcObject && el.readyState === el.HAVE_ENOUGH_DATA;
    }
    return !!el.getAttribute("src") && el.complete && el.naturalWidth > 0;
  }

  function tryDecodeFrame() {
    // Jangan scan jika CAMERA BOTTOM tidak punya gambar sama sekali.
    if (!isFrameReady(videoBottom)) return;

    const { w, h } = getFrameSize(videoBottom);
    if (!w || !h) return;

    // Resolusi khusus untuk proses QR.
    // Tampilan kamera tetap menggunakan resolusi aslinya.
    const scanW = 360;
    const scanH = Math.round((h / w) * scanW);

    if (
      scanCanvas.width !== scanW ||
      scanCanvas.height !== scanH
    ) {
      scanCanvas.width = scanW;
      scanCanvas.height = scanH;
    }

    scanCtx.drawImage(
      videoBottom,
      0,
      0,
      scanW,
      scanH
    );

    const imageData = scanCtx.getImageData(
      0,
      0,
      scanW,
      scanH
    );

    const result = jsQR(
      imageData.data,
      scanW,
      scanH,
      {
        inversionAttempts: "dontInvert",
      }
    );

    const overlay = document.getElementById("qrOverlay");
    const overlayData = document.getElementById("qrOverlayData");
    const now = Date.now();

    if (result && result.data) {
      lastDetectionTime = now;
      overlay.style.display = "block";

      if (result.data !== lastDecodedText) {
        lastDecodedText = result.data;
        overlayData.textContent = result.data;

        // Kirim data QR ke telemetry (WebSocket -> backend Raspberry Pi).
        Telemetry.send({
          type: "qr_detected",
          data: result.data,
          ts: now,
        });
      }
    } else {
      // Sembunyikan overlay jika tidak ada deteksi dalam 1.5 detik terakhir
      if (now - lastDetectionTime > 1500) {
        overlay.style.display = "none";
        lastDecodedText = null;
      }
    }
  }

  return { start };
})();
