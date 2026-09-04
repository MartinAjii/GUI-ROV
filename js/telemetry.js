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

  // --- Trajectory Logic ---
  const MAX_TRAJECTORY_POINTS = 500;
  let trajectoryPoints = [];
  let trajectoryCanvas = null;
  let trajectoryCtx = null;
  let pulsePhase = 0;
  let trajectoryInitialized = false;

  function initTrajectory() {
    if (trajectoryInitialized) return;
    trajectoryCanvas = document.getElementById("trajectoryCanvas");
    if (!trajectoryCanvas) return;
    
    // Handle HDPI displays properly if we wanted, but standard canvas scale is fine for this
    trajectoryCtx = trajectoryCanvas.getContext("2d");

    const btnReset = document.getElementById("btnResetPath");
    if (btnReset) {
      btnReset.addEventListener("click", () => {
        trajectoryPoints = [];
      });
    }

    requestAnimationFrame(animateTrajectory);
    trajectoryInitialized = true;
  }

  function handlePositionMessage(data) {
    if (typeof data.x === "number" && typeof data.y === "number") {
      trajectoryPoints.push({ x: data.x, y: data.y });
      if (trajectoryPoints.length > MAX_TRAJECTORY_POINTS) {
        trajectoryPoints.shift();
      }
    }
  }

  function animateTrajectory() {
    pulsePhase += 0.05;
    drawTrajectory();
    requestAnimationFrame(animateTrajectory);
  }

  function drawTrajectory() {
    if (!trajectoryCtx || !trajectoryCanvas) return;

    // Read internal drawing buffer size
    const w = trajectoryCanvas.width;
    const h = trajectoryCanvas.height;
    
    trajectoryCtx.clearRect(0, 0, w, h);

    if (trajectoryPoints.length === 0) {
       return;
    }

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let p of trajectoryPoints) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }

    const padding = 15;
    const rangeX = (maxX - minX) || 1;
    const rangeY = (maxY - minY) || 1;
    
    const scale = Math.min((w - padding * 2) / rangeX, (h - padding * 2) / rangeY);
    
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const toCanvas = (p) => {
       return {
         x: w/2 + (p.x - centerX) * scale,
         y: h/2 - (p.y - centerY) * scale
       };
    };

    // Draw Path
    trajectoryCtx.beginPath();
    trajectoryCtx.strokeStyle = "rgba(34, 211, 238, 0.6)";
    trajectoryCtx.lineWidth = 1.5;
    trajectoryCtx.lineJoin = "round";

    for (let i = 0; i < trajectoryPoints.length; i++) {
      const cp = toCanvas(trajectoryPoints[i]);
      if (i === 0) trajectoryCtx.moveTo(cp.x, cp.y);
      else trajectoryCtx.lineTo(cp.x, cp.y);
    }
    trajectoryCtx.stroke();

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
