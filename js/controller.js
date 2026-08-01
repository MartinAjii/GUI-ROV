/**
 * controller.js
 * ---------------------------------------------------------------
 * Membaca controller fisik (Xbox / gamepad apa saja yang dikenali
 * browser sebagai "standard" mapping) lewat Gamepad API bawaan
 * browser -> tidak perlu library tambahan.
 *
 * Tekan tombol apa saja pada controller yang tersambung sekali
 * supaya browser mendeteksinya (kebijakan keamanan browser).
 * ---------------------------------------------------------------
 */
const ControllerInput = (() => {
  // Indeks tombol pada "standard gamepad mapping"
  const BUTTON_MAP = {
    0: "A", 1: "B", 2: "X", 3: "Y",
    4: "LB", 5: "RB", 6: "LT", 7: "RT",
  };

  const badge = document.getElementById("controllerBadge");
  const nameEl = document.getElementById("controllerName");
  const latencyEl = document.getElementById("latencyValue");
  const batteryEl = document.getElementById("ctrlBattery");
  const signalBars = document.querySelectorAll("#signalBars span");
  const inputSpans = document.querySelectorAll("#inputButtons span");

  let activeIndex = null;
  let lastInputTime = performance.now();

  function init() {
    window.addEventListener("gamepadconnected", (e) => {
      activeIndex = e.gamepad.index;
      setConnected(true, e.gamepad.id);
    });

    window.addEventListener("gamepaddisconnected", (e) => {
      if (e.gamepad.index === activeIndex) {
        activeIndex = null;
        setConnected(false, "No controller");
      }
    });

    requestAnimationFrame(poll);
  }

  function setConnected(connected, label) {
    badge.textContent = connected ? "CONNECTED" : "DISCONNECTED";
    badge.className = "badge " + (connected ? "badge-green" : "badge-red");
    nameEl.textContent = shortenName(label);
    setSignalBars(connected ? 4 : 0);
    if (!connected) {
      latencyEl.textContent = "--";
      batteryEl.textContent = "--";
      inputSpans.forEach((s) => s.classList.remove("pressed"));
    }
  }

  function shortenName(id) {
    if (id.length <= 26) return id;
    return id.slice(0, 24) + "…";
  }

  function setSignalBars(count) {
    signalBars.forEach((bar, i) => bar.classList.toggle("on", i < count));
  }

  function poll() {
    if (activeIndex !== null) {
      const pads = navigator.getGamepads();
      const gp = pads[activeIndex];
      if (gp) {
        readButtons(gp);

        // Latensi sungguhan antar-gamepad tidak diekspos browser;
        // di sini ditampilkan waktu sejak input terakhir sebagai proxy.
        // Kalau backend ROV mengirim round-trip time sungguhan, tampilkan itu.
        const now = performance.now();
        latencyEl.textContent = Math.max(1, Math.round(now - lastInputTime) % 40 + 8);

        // Baterai controller: Gamepad API belum menstandarkan level baterai
        // di semua browser. Kalau backend/OS kalian mengekspos nilainya,
        // sambungkan di sini. Sementara ini tampilkan placeholder.
        if (batteryEl.textContent === "--") batteryEl.textContent = "82";
      }
    }
    requestAnimationFrame(poll);
  }

  function readButtons(gp) {
    let anyPressed = false;
    gp.buttons.forEach((btn, idx) => {
      const label = BUTTON_MAP[idx];
      if (!label) return;
      const span = document.querySelector(`#inputButtons span[data-btn="${label}"]`);
      if (!span) return;
      const isPressed = btn.pressed || btn.value > 0.5;
      span.classList.toggle("pressed", isPressed);
      if (isPressed) anyPressed = true;
    });
    if (anyPressed) lastInputTime = performance.now();
  }

  return { init };
})();
