// Titik masuk aplikasi. Dijalankan setelah seluruh DOM siap.

document.addEventListener("DOMContentLoaded", async () => {
  const params = new URLSearchParams(window.location.search);
  const teamName = params.get("team") || CONFIG.teamName;
  document.getElementById("teamName").textContent = teamName;

  Gripper.init();
  ControllerInput.init();
  MissionTrack.init();
  Telemetry.connect();

  try {
    await CameraQR.start();
  } catch (err) {
    console.error("Gagal menyalakan kamera:", err);
  }
});
