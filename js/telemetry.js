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
        handleTelemetryMessage(data);
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
