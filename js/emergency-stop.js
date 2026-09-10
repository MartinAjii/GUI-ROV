// Software DISARM: never show completion from a button click or ACK alone.
const EmergencyStop = (() => {
  let button, status, state;
  let socketOpen = false;
  let lastTelemetry = null;
  let receivedAt = 0;
  let waitingId = null;
  let requestedAt = 0;
  let error = "";

  function init() {
    button = document.getElementById("btnStopDisarm");
    status = document.getElementById("stopStatus");
    state = document.getElementById("stopArmState");
    button.addEventListener("click", requestStop);
    setInterval(render, 250);
    render();
  }

  function setConnection(open) {
    socketOpen = open;
    lastTelemetry = null;
    receivedAt = 0;
    if (!open && waitingId) {
      error = "Koneksi putus; DISARM belum terkonfirmasi. Gunakan emergency stop fisik.";
      waitingId = null;
    }
    render();
  }

  function onTelemetry(data) {
    lastTelemetry = data;
    receivedAt = performance.now();
    if (waitingId && data.stop?.id === waitingId) waitingId = null;
    render();
  }

  function onResult(data) {
    if (!waitingId || data.id !== waitingId) return;
    waitingId = null;
    error = data.error || "";
    if (data.stop && lastTelemetry) lastTelemetry.stop = data.stop;
    render();
  }

  function available() {
    return socketOpen && lastTelemetry?.connected === true
      && lastTelemetry?.stop_available === true
      && typeof lastTelemetry?.armed === "boolean"
      && performance.now() - receivedAt < 2000;
  }

  function requestStop() {
    if (!available() || waitingId || lastTelemetry?.stop?.phase === "pending") return;
    error = "";
    waitingId = `stop-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    requestedAt = performance.now();
    if (!Telemetry.send({type: "command", command: "disarm", id: waitingId})) {
      waitingId = null;
      error = "Gagal mengirim DISARM. Gunakan emergency stop fisik.";
    }
    render();
  }

  function render() {
    if (!button) return;
    if (waitingId && performance.now() - requestedAt >= 7000) {
      waitingId = null;
      error = "Backend tidak mengonfirmasi permintaan. DISARM belum terkonfirmasi.";
    }
    const fresh = available();
    const stop = lastTelemetry?.stop;
    const pending = Boolean(waitingId) || stop?.phase === "pending";
    button.disabled = !fresh || pending;
    button.textContent = pending && fresh ? "MENUNGGU DISARM…" : "STOP / DISARM";
    state.textContent = !fresh ? "STATUS TIDAK DIKETAHUI"
      : lastTelemetry.armed ? "ARMED" : "DISARMED";
    state.dataset.state = !fresh ? "unknown" : lastTelemetry.armed ? "armed" : "disarmed";

    let message;
    if (!fresh) {
      message = "Tidak ada konfirmasi Pixhawk terbaru. STOP GUI tidak tersedia; gunakan emergency stop fisik.";
    } else if (waitingId) {
      message = "Permintaan dikirim; menunggu respons backend…";
    } else if (error) {
      message = error;
    } else if (stop?.phase === "pending") {
      message = stop.message;
    } else if (lastTelemetry.armed === false) {
      message = "Pixhawk melaporkan DISARM. Daya listrik ROV tetap menyala.";
    } else if (stop?.phase === "confirmed") {
      message = "Pixhawk kembali ARMED. DISARM sebelumnya tidak lagi berlaku.";
    } else if (["rejected", "unconfirmed"].includes(stop?.phase)) {
      message = `${stop.message} Gunakan emergency stop fisik bila perlu.`;
    } else {
      message = "Klik sekali untuk meminta DISARM ke Pixhawk.";
    }
    // Avoid repeatedly announcing unchanged text to screen readers.
    if (status.textContent !== message) status.textContent = message;
  }

  return {init, setConnection, onTelemetry, onResult};
})();
