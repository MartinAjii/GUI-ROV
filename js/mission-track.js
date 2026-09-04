/**
 * mission-track.js
 * ---------------------------------------------------------------
 * Panel "MISSION HISTORY": jejak rute yang dilalui ROV (ala peta
 * Strava) + galeri screenshot manual dari kedua kamera.
 *
 * TRACK (dead-reckoning):
 *   ROV ini tidak punya GPS bawah air, jadi posisi (x, y) dalam meter
 *   dihitung sendiri di browser tiap TICK_MS, dari:
 *     - yaw sekarang (dibaca dari #telYaw, hasil ATTITUDE Pixhawk)
 *     - vektor stick kiri controller (ControllerInput.getMovement())
 *     - CONFIG.track.maxSpeedMps (perkiraan kecepatan full throttle)
 *   Ini ESTIMASI arah eksplorasi, bukan koordinat presisi — akan makin
 *   drift kalau misi berlangsung lama. Kalau nanti Pixhawk kalian
 *   punya sumber posisi asli (mis. GPS di surface float / DVL) dan
 *   dikirim backend sebagai field lat/lon di pesan telemetry, tinggal
 *   ganti logika tick() di bawah untuk pakai itu.
 *
 * SCREENSHOT:
 *   Tombol CAPTURE mengambil frame CAMERA BOTTOM & CAMERA WALL saat
 *   itu juga (client-side, lewat <canvas>), lalu dicatat ke galeri
 *   berikut posisi track, depth, dan waktunya — bisa diunduh per item.
 *
 * Baik track maupun galeri di-autosave ke localStorage (kalau
 * CONFIG.track.autosaveEnabled) supaya tidak hilang kalau halaman
 * ke-refresh tanpa sengaja saat lomba. Tombol RESET menghapus semuanya
 * dan memulai misi baru dari titik (0,0).
 * ---------------------------------------------------------------
 */
const MissionTrack = (() => {
  const TICK_MS = 500;
  const MAX_POINTS = 6000; // ~50 menit misi pada interval 500ms
  const MAX_GALLERY = 30;
  const STORAGE_KEY = "rovMissionTrack_v1";

  const canvas = document.getElementById("trackCanvas");
  const ctx = canvas ? canvas.getContext("2d") : null;
  const distanceEl = document.getElementById("trackDistance");
  const btnCapture = document.getElementById("btnCapture");
  const btnReset = document.getElementById("btnResetTrack");
  const galleryList = document.getElementById("galleryList");
  const galleryEmpty = document.getElementById("galleryEmpty");

  let pos = { x: 0, y: 0 };
  let path = [{ x: 0, y: 0 }];
  let totalDistance = 0;
  let gallery = []; // terbaru di index 0
  let tickHandle = null;
  let tickCount = 0;

  function init() {
    if (!canvas || !ctx) return; // panel tidak ada di halaman ini

    load();
    redrawTrack();
    renderGallery();
    updateDistanceLabel();

    btnCapture?.addEventListener("click", capture);
    btnReset?.addEventListener("click", () => {
      if (confirm("Reset track & hapus semua screenshot misi ini?")) reset();
    });

    window.addEventListener("resize", redrawTrack);

    tickHandle = setInterval(tick, TICK_MS);
  }

  /*
   * ============================================================
   * DEAD-RECKONING TICK
   * ============================================================
   */
  function tick() {
    const yawDeg = parseFloat(getText("telYaw")) || 0;
    const heading = (yawDeg * Math.PI) / 180;
    const move =
      window.ControllerInput && ControllerInput.getMovement
        ? ControllerInput.getMovement()
        : { forward: 0, strafe: 0 };

    const speed = (CONFIG.track && CONFIG.track.maxSpeedMps) || 0.6;
    const dt = TICK_MS / 1000;

    // "forward" = arah hadap ROV (heading), "strafe" = tegak lurus
    // ke kanan dari heading. 0° = utara/atas layar, searah jarum jam.
    const vx = (move.forward * Math.sin(heading) + move.strafe * Math.cos(heading)) * speed;
    const vy = (-move.forward * Math.cos(heading) + move.strafe * Math.sin(heading)) * speed;
    const dx = vx * dt;
    const dy = vy * dt;

    if (dx !== 0 || dy !== 0) {
      pos.x += dx;
      pos.y += dy;
      totalDistance += Math.hypot(dx, dy);
    }

    path.push({ x: pos.x, y: pos.y });
    if (path.length > MAX_POINTS) path.shift();

    redrawTrack();
    updateDistanceLabel();

    tickCount++;
    if (tickCount % 4 === 0) savePath(); // throttle write localStorage (~2s)
  }

  function updateDistanceLabel() {
    if (!distanceEl) return;
    distanceEl.textContent =
      totalDistance >= 1000
        ? (totalDistance / 1000).toFixed(2) + " km"
        : Math.round(totalDistance) + " m";
  }

  /*
   * ============================================================
   * GAMBAR TRACK DI CANVAS
   * ============================================================
   */
  function redrawTrack() {
    if (!canvas || !ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 300;
    const cssH = canvas.clientHeight || 200;
    if (canvas.width !== cssW * dpr || canvas.height !== cssH * dpr) {
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const pad = 22;
    const xs = path.map((p) => p.x);
    const ys = path.map((p) => p.y);
    let minX = Math.min(0, ...xs);
    let maxX = Math.max(0, ...xs);
    let minY = Math.min(0, ...ys);
    let maxY = Math.max(0, ...ys);

    // Jaga supaya track kecil/diam tetap kelihatan (bounding box minimal 2m).
    const spanX = Math.max(maxX - minX, 2);
    const spanY = Math.max(maxY - minY, 2);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    minX = cx - spanX / 2;
    maxX = cx + spanX / 2;
    minY = cy - spanY / 2;
    maxY = cy + spanY / 2;

    const scale = Math.min((cssW - pad * 2) / (maxX - minX), (cssH - pad * 2) / (maxY - minY));

    const toPx = (p) => ({
      px: cssW / 2 + (p.x - cx) * scale,
      py: cssH / 2 + (p.y - cy) * scale,
    });

    // Grid tipis biar ada rasa "peta"
    ctx.strokeStyle = "rgba(124,139,163,0.12)";
    ctx.lineWidth = 1;
    for (let gx = 0; gx <= cssW; gx += 30) {
      ctx.beginPath();
      ctx.moveTo(gx, 0);
      ctx.lineTo(gx, cssH);
      ctx.stroke();
    }
    for (let gy = 0; gy <= cssH; gy += 30) {
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(cssW, gy);
      ctx.stroke();
    }

    // Garis jejak
    if (path.length > 1) {
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.beginPath();
      path.forEach((p, i) => {
        const { px, py } = toPx(p);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      ctx.stroke();
    }

    // Marker screenshot (titik kuning)
    gallery.forEach((entry) => {
      const { px, py } = toPx({ x: entry.x, y: entry.y });
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#f59e0b";
      ctx.fill();
    });

    // Titik START
    const start = toPx(path[0]);
    ctx.beginPath();
    ctx.arc(start.px, start.py, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#22c55e";
    ctx.fill();

    // Posisi ROV sekarang
    const cur = toPx(pos);
    ctx.beginPath();
    ctx.arc(cur.px, cur.py, 6, 0, Math.PI * 2);
    ctx.fillStyle = "#e8edf5";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cur.px, cur.py, 6, 0, Math.PI * 2);
    ctx.strokeStyle = "#22d3ee";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  /*
   * ============================================================
   * SCREENSHOT
   * ============================================================
   */
  function grabFrame(elId, maxWidth) {
    const el = document.getElementById(elId);
    if (!el) return null;

    const isVideo = el.tagName === "VIDEO";
    const w = isVideo ? el.videoWidth : el.naturalWidth;
    const h = isVideo ? el.videoHeight : el.naturalHeight;
    if (!w || !h) return null;

    const scale = maxWidth && w > maxWidth ? maxWidth / w : 1;
    const outCanvas = document.createElement("canvas");
    outCanvas.width = Math.round(w * scale);
    outCanvas.height = Math.round(h * scale);
    outCanvas.getContext("2d").drawImage(el, 0, 0, outCanvas.width, outCanvas.height);

    try {
      return outCanvas.toDataURL("image/jpeg", 0.85);
    } catch (err) {
      console.warn(`Gagal capture ${elId} (kemungkinan CORS pada stream):`, err);
      return null;
    }
  }

  function capture() {
    const bottom = grabFrame("camBottom");
    const wall = grabFrame("camWall");

    if (!bottom && !wall) {
      flashCaptureBtn(false);
      return;
    }

    const entry = {
      id: Date.now(),
      time: new Date().toLocaleTimeString("id-ID", { hour12: false }),
      depth: getText("telDepth"),
      yaw: getText("telYaw"),
      x: pos.x,
      y: pos.y,
      bottom,
      wall,
    };

    gallery.unshift(entry);
    if (gallery.length > MAX_GALLERY) gallery.length = MAX_GALLERY;

    renderGallery();
    redrawTrack();
    saveGallery();
    flashCaptureBtn(true);
  }

  function flashCaptureBtn(success) {
    if (!btnCapture) return;
    const original = btnCapture.textContent;
    btnCapture.textContent = success ? "✅ SAVED" : "⚠ NO SIGNAL";
    btnCapture.disabled = true;
    setTimeout(() => {
      btnCapture.textContent = original;
      btnCapture.disabled = false;
    }, 700);
  }

  function renderGallery() {
    if (!galleryList) return;

    if (galleryEmpty) galleryEmpty.style.display = gallery.length ? "none" : "block";
    galleryList.innerHTML = "";

    gallery.forEach((entry) => {
      const card = document.createElement("div");
      card.className = "gallery-item";

      const thumbSrc = entry.bottom || entry.wall;
      const links = [];
      if (entry.bottom) links.push(`<a download="rov_bottom_${entry.id}.jpg" href="${entry.bottom}">BOTTOM</a>`);
      if (entry.wall) links.push(`<a download="rov_wall_${entry.id}.jpg" href="${entry.wall}">WALL</a>`);

      card.innerHTML = `
        <img src="${thumbSrc}" alt="ROV capture ${entry.time}" loading="lazy" />
        <div class="gallery-meta">
          <span>${entry.time}</span>
          <span>${entry.depth}m</span>
        </div>
        <div class="gallery-actions">${links.join("")}</div>
      `;
      galleryList.appendChild(card);
    });
  }

  /*
   * ============================================================
   * RESET
   * ============================================================
   */
  function reset() {
    pos = { x: 0, y: 0 };
    path = [{ x: 0, y: 0 }];
    totalDistance = 0;
    gallery = [];

    redrawTrack();
    updateDistanceLabel();
    renderGallery();
    clearStorage();
  }

  /*
   * ============================================================
   * AUTOSAVE (localStorage) — best-effort, tidak boleh mengganggu
   * jalannya dashboard kalau gagal (mis. storage penuh/disabled).
   * ============================================================
   */
  function savePath() {
    if (!CONFIG.track?.autosaveEnabled) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const saved = raw ? JSON.parse(raw) : {};
      saved.path = path;
      saved.pos = pos;
      saved.totalDistance = totalDistance;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    } catch (err) {
      console.warn("Autosave track gagal (lanjut tanpa localStorage):", err);
    }
  }

  function saveGallery() {
    if (!CONFIG.track?.autosaveEnabled) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const saved = raw ? JSON.parse(raw) : {};
      saved.gallery = gallery;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
    } catch (err) {
      // Kemungkinan besar quota localStorage penuh gara-gara banyak
      // screenshot resolusi tinggi — galeri tetap ada di memori/tab
      // ini, cuma tidak ke-autosave lagi.
      console.warn("Autosave galeri gagal (kemungkinan storage penuh):", err);
    }
  }

  function load() {
    if (!CONFIG.track?.autosaveEnabled) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (Array.isArray(saved.path) && saved.path.length) path = saved.path;
      if (saved.pos) pos = saved.pos;
      if (typeof saved.totalDistance === "number") totalDistance = saved.totalDistance;
      if (Array.isArray(saved.gallery)) gallery = saved.gallery;
    } catch (err) {
      console.warn("Gagal load autosave track sebelumnya:", err);
    }
  }

  function clearStorage() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      // abaikan
    }
  }

  function getText(id) {
    const el = document.getElementById(id);
    return el ? el.textContent : "0";
  }

  return { init, capture, reset };
})();
