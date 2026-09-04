/**
 * telemetry.js
 * ---------------------------------------------------------------
 * Mengelola koneksi WebSocket ke backend ROV dan memperbarui
 * elemen-elemen: ROV STATUS, BATTERY, MISSION TIME, DEPTH, PITCH,
 * ROLL, YAW.
 *
 * Format pesan JSON yang diharapkan dari backend (contoh):
 * {
 *   "type": "telemetry",
 *   "depth": 1.8,
 *   "pitch": 1.0,
 *   "roll": 1.8,
 *   "yaw": 44.5,
 *   "battery": 14.8,
 *   "connected": true
 * }
 * ---------------------------------------------------------------
 */
const Telemetry = (() => {
  let socket = null;
  let missionStartTime = null;
  let missionTimerHandle = null;
  let simulationHandle = null;

  function connect() {
    initTrajectory();
    if (!CONFIG.websocketUrl) {
      setRovStatus(false, "No backend");
      if (CONFIG.useSimulationWhenOffline) startSimulation();
      return;
    }

    socket = new WebSocket(CONFIG.websocketUrl);

    socket.addEventListener("open", () => {
      setRovStatus(true, "Connected");
      startMissionTimer();
      stopSimulation();
    });

    socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "position") {
          handlePositionMessage(data);
        } else {
          handleTelemetryMessage(data);
        }
      } catch (err) {
        console.warn("Pesan telemetry tidak valid:", event.data);
      }
    });

    socket.addEventListener("close", () => {
      setRovStatus(false, "Disconnected");
      stopMissionTimer();
      setTimeout(connect, CONFIG.wsReconnectDelayMs);
      if (CONFIG.useSimulationWhenOffline) startSimulation();
    });

    socket.addEventListener("error", () => socket.close());
  }

  // --- Trajectory & Gallery Logic ---
  const MAX_TRAJECTORY_POINTS = 6000;
  const MAX_GALLERY = 30;
  const STORAGE_KEY = "rovMissionTrack_v2";
  
  let trajectoryPoints = [];
  let gallery = [];
  let trajectoryCanvas = null;
  let trajectoryCtx = null;
  let pulsePhase = 0;
  let trajectoryInitialized = false;

  function loadStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (Array.isArray(saved.path)) trajectoryPoints = saved.path;
        if (Array.isArray(saved.gallery)) gallery = saved.gallery;
      }
    } catch(e) {}
  }

  function saveStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        path: trajectoryPoints,
        gallery: gallery
      }));
    } catch(e) {}
  }

  function initTrajectory() {
    if (trajectoryInitialized) return;
    loadStorage();
    
    trajectoryCanvas = document.getElementById("trajectoryCanvas");
    if (!trajectoryCanvas) return;
    trajectoryCtx = trajectoryCanvas.getContext("2d");

    const btnReset = document.getElementById("btnResetPath");
    if (btnReset) {
      btnReset.addEventListener("click", () => {
        if (confirm("Reset track & delete all screenshots?")) {
          trajectoryPoints = [];
          gallery = [];
          saveStorage();
          renderGallery();
        }
      });
    }

    const btnCapture = document.getElementById("btnCapture");
    if (btnCapture) {
      btnCapture.addEventListener("click", capture);
    }
    
    renderGallery();
    requestAnimationFrame(animateTrajectory);
    trajectoryInitialized = true;
  }
  
  function grabFrame(elId) {
    const el = document.getElementById(elId);
    if (!el || el.tagName !== "VIDEO" || !el.videoWidth) return null;
    const outCanvas = document.createElement("canvas");
    outCanvas.width = 320; // scale down
    outCanvas.height = Math.round((el.videoHeight / el.videoWidth) * 320);
    outCanvas.getContext("2d").drawImage(el, 0, 0, outCanvas.width, outCanvas.height);
    try { return outCanvas.toDataURL("image/jpeg", 0.7); } catch(e) { return null; }
  }

  function capture() {
    const bottom = grabFrame("camBottom");
    const wall = grabFrame("camWall");
    if (!bottom && !wall) return;
    
    let currentPos = trajectoryPoints.length ? trajectoryPoints[trajectoryPoints.length-1] : {x:0, y:0};
    
    const entry = {
      id: Date.now(),
      time: new Date().toLocaleTimeString("id-ID", { hour12: false }),
      depth: document.getElementById("telDepth")?.textContent || "0.0",
      x: currentPos.x,
      y: currentPos.y,
      bottom,
      wall
    };
    
    gallery.unshift(entry);
    if (gallery.length > MAX_GALLERY) gallery.length = MAX_GALLERY;
    
    saveStorage();
    renderGallery();
  }

  function renderGallery() {
    const list = document.getElementById("galleryList");
    const empty = document.getElementById("galleryEmpty");
    if (!list || !empty) return;
    
    empty.style.display = gallery.length ? "none" : "block";
    list.innerHTML = "";
    
    gallery.forEach(entry => {
      const card = document.createElement("div");
      card.className = "gallery-item";
      const thumbSrc = entry.bottom || entry.wall;
      const links = [];
      if (entry.bottom) links.push(`<a download="rov_bottom_${entry.id}.jpg" href="${entry.bottom}">BOTTOM</a>`);
      if (entry.wall) links.push(`<a download="rov_wall_${entry.id}.jpg" href="${entry.wall}">WALL</a>`);
      card.innerHTML = `
        <img src="${thumbSrc}" loading="lazy" />
        <div class="gallery-meta">
          <span>${entry.time}</span>
          <span>${entry.depth}m</span>
        </div>
        <div class="gallery-actions">${links.join("")}</div>
      `;
      list.appendChild(card);
    });
  }

  function handlePositionMessage(data) {
    if (typeof data.x === "number" && typeof data.y === "number") {
      trajectoryPoints.push({ x: data.x, y: data.y });
      if (trajectoryPoints.length > MAX_TRAJECTORY_POINTS) {
        trajectoryPoints.shift();
      }
      if (trajectoryPoints.length % 5 === 0) saveStorage(); // throttle saving
    }
  }

  function animateTrajectory() {
    pulsePhase += 0.05;
    drawTrajectory();
    requestAnimationFrame(animateTrajectory);
  }

  function drawTrajectory() {
    if (!trajectoryCtx || !trajectoryCanvas) return;
    const w = trajectoryCanvas.width;
    const h = trajectoryCanvas.height;
    trajectoryCtx.clearRect(0, 0, w, h);

    // grid lines
    trajectoryCtx.strokeStyle = "rgba(124,139,163,0.12)";
    trajectoryCtx.lineWidth = 1;
    for (let gx = 0; gx <= w; gx += 30) {
      trajectoryCtx.beginPath(); trajectoryCtx.moveTo(gx, 0); trajectoryCtx.lineTo(gx, h); trajectoryCtx.stroke();
    }
    for (let gy = 0; gy <= h; gy += 30) {
      trajectoryCtx.beginPath(); trajectoryCtx.moveTo(0, gy); trajectoryCtx.lineTo(w, gy); trajectoryCtx.stroke();
    }

    if (trajectoryPoints.length === 0) return;

    let minX = 0, maxX = 0, minY = 0, maxY = 0;
    if (trajectoryPoints.length) {
       minX = Math.min(...trajectoryPoints.map(p=>p.x));
       maxX = Math.max(...trajectoryPoints.map(p=>p.x));
       minY = Math.min(...trajectoryPoints.map(p=>p.y));
       maxY = Math.max(...trajectoryPoints.map(p=>p.y));
    }
    
    // minimum bounding box to avoid infinite scale
    const spanX = Math.max(maxX - minX, 2);
    const spanY = Math.max(maxY - minY, 2);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    minX = cx - spanX / 2;
    maxX = cx + spanX / 2;
    minY = cy - spanY / 2;
    maxY = cy + spanY / 2;

    const padding = 15;
    const scale = Math.min((w - padding * 2) / spanX, (h - padding * 2) / spanY);
    
    const toCanvas = (p) => ({
      x: w/2 + (p.x - cx) * scale,
      y: h/2 - (p.y - cy) * scale
    });

    // Draw path
    trajectoryCtx.beginPath();
    trajectoryCtx.strokeStyle = "rgba(34, 211, 238, 0.6)";
    trajectoryCtx.lineWidth = 1.5;
    trajectoryCtx.lineJoin = "round";
    trajectoryPoints.forEach((p, i) => {
      const cp = toCanvas(p);
      if (i === 0) trajectoryCtx.moveTo(cp.x, cp.y);
      else trajectoryCtx.lineTo(cp.x, cp.y);
    });
    trajectoryCtx.stroke();
    
    // Draw gallery markers (yellow dots)
    gallery.forEach(entry => {
      const gP = toCanvas({x: entry.x, y: entry.y});
      trajectoryCtx.beginPath();
      trajectoryCtx.arc(gP.x, gP.y, 4, 0, Math.PI * 2);
      trajectoryCtx.fillStyle = "#f59e0b";
      trajectoryCtx.fill();
    });

    // Start point
    const startP = toCanvas(trajectoryPoints[0]);
    trajectoryCtx.beginPath();
    trajectoryCtx.arc(startP.x, startP.y, 3.5, 0, Math.PI * 2);
    trajectoryCtx.fillStyle = "rgba(255, 255, 255, 0.8)";
    trajectoryCtx.fill();

    // Current point
    const currP = toCanvas(trajectoryPoints[trajectoryPoints.length - 1]);
    const glowRadius = 4 + (Math.sin(pulsePhase) + 1) * 2;
    trajectoryCtx.beginPath();
    trajectoryCtx.arc(currP.x, currP.y, glowRadius, 0, Math.PI * 2);
    trajectoryCtx.fillStyle = "rgba(239, 68, 68, 0.25)";
    trajectoryCtx.fill();
    trajectoryCtx.beginPath();
    trajectoryCtx.arc(currP.x, currP.y, 3.5, 0, Math.PI * 2);
    trajectoryCtx.fillStyle = "#ef4444";
    trajectoryCtx.fill();
  }

  function send(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    } else {
      console.log("[SIM] would send to ROV:", payload);
    }
  }

  function handleTelemetryMessage(data) {
    if (typeof data.depth === "number") setText("telDepth", data.depth.toFixed(1));
    if (typeof data.pitch === "number") setText("telPitch", signed(data.pitch));
    if (typeof data.roll === "number") setText("telRoll", signed(data.roll));
    if (typeof data.yaw === "number") setText("telYaw", data.yaw.toFixed(1));
    if (typeof data.battery === "number") setText("batteryValue", data.battery.toFixed(1));
    if (typeof data.connected === "boolean") setRovStatus(data.connected);

    if (data.gripper) Gripper.setState(data.gripper, "ROV");
  }

  function setRovStatus(connected, label) {
    const dot = document.getElementById("rovStatusDot");
    const text = document.getElementById("rovStatusText");
    dot.className = "dot " + (connected ? "dot-green" : "dot-red");
    text.textContent = label || (connected ? "Connected" : "Disconnected");
  }

  function startMissionTimer() {
    missionStartTime = Date.now();
    stopMissionTimer();
    missionTimerHandle = setInterval(() => {
      const elapsed = Math.floor((Date.now() - missionStartTime) / 1000);
      const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
      const ss = String(elapsed % 60).padStart(2, "0");
      setText("missionTime", `${mm}:${ss}`);
    }, 1000);
  }

  function stopMissionTimer() {
    if (missionTimerHandle) clearInterval(missionTimerHandle);
  }

  // Data acak untuk latihan tampilan sebelum backend ROV siap.
  function startSimulation() {
    if (simulationHandle) return;
    startMissionTimer();
    simulationHandle = setInterval(() => {
      handleTelemetryMessage({
        depth: 1.5 + Math.random() * 0.6,
        pitch: (Math.random() - 0.5) * 4,
        roll: (Math.random() - 0.5) * 4,
        yaw: Math.random() * 360,
        battery: 14.5 + Math.random() * 0.5,
      });
    }, 1500);
  }

  function stopSimulation() {
    if (simulationHandle) clearInterval(simulationHandle);
    simulationHandle = null;
  }

  function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function signed(n) {
    return (n >= 0 ? "+" : "") + n.toFixed(1);
  }

  return { connect, send };
})();
