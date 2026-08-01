/**
 * gripper.js
 * ---------------------------------------------------------------
 * Mengatur tampilan & perintah untuk panel GRIPPER.
 * setState() dipanggil baik dari klik tombol UI maupun dari pesan
 * telemetry ROV (misalnya kalau gripper digerakkan lewat controller
 * fisik, backend bisa mengirim balik statusnya supaya UI tetap sinkron).
 * ---------------------------------------------------------------
 */
const Gripper = (() => {
  const btnOpen = document.getElementById("btnOpen");
  const btnClosed = document.getElementById("btnClosed");
  const badge = document.getElementById("gripperBadge");
  const handle = document.getElementById("gripperHandle");
  const sourceLabel = document.getElementById("gripperSource");

  let state = "open"; // "open" | "closed"

  function init() {
    btnOpen.addEventListener("click", () => setState("open", "UI"));
    btnClosed.addEventListener("click", () => setState("closed", "UI"));
  }

  function setState(newState, source) {
    state = newState;
    const isOpen = state === "open";

    btnOpen.classList.toggle("active", isOpen);
    btnClosed.classList.toggle("active", !isOpen);
    badge.textContent = isOpen ? "OPEN" : "CLOSED";
    badge.className = "badge " + (isOpen ? "badge-green" : "badge-idle");
    handle.style.left = isOpen ? "30%" : "70%";
    sourceLabel.textContent = `LAST COMMAND VIA ${source === "UI" ? "DASHBOARD" : source.toUpperCase()}`;

    if (source === "UI") {
      Telemetry.send({ type: "gripper_command", state });
    }
  }

  return { init, setState, getState: () => state };
})();
