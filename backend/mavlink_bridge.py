"""
mavlink_bridge.py
---------------------------------------------------------------
Jembatan antara Pixhawk (lewat MAVLink/USB serial) dan dashboard
web (lewat WebSocket) di laptop topside.

Alur:
  Pixhawk --USB serial--> Raspberry Pi (thread pembaca MAVLink)
                              |
                              v
                    shared state (dict + lock)
                              |
                              v
        WebSocket server (asyncio) --LAN/hAP lite--> dashboard browser

Dashboard mengirim balik dua jenis pesan lewat WebSocket:
  { "type": "gripper_command", "state": "open" | "closed" }
  { "type": "qr_detected", "data": "...", "ts": 1735689900000 }

Jalankan:
    python3 mavlink_bridge.py

Cek koneksi Pixhawk dulu pakai Mission Planner / PuTTY sebelum
menjalankan skrip ini, supaya kalau MAVLink tidak konek, kalian
tahu masalahnya di kabel/port, bukan di skrip ini.
---------------------------------------------------------------
"""

import asyncio
import csv
import json
import math
import os
import queue
import threading
import time
from datetime import datetime

import websockets
from pymavlink import mavutil

import config

# ============================================================
# STATE BERSAMA (ditulis oleh thread MAVLink, dibaca oleh asyncio)
# ============================================================
state_lock = threading.Lock()
state = {
    "depth": 0.0,
    "pitch": 0.0,
    "roll": 0.0,
    "yaw": 0.0,
    "battery": 0.0,
    "connected": False,
    "gripper": None,  # diisi kalau Pixhawk melaporkan posisi servo gripper
}

# Antrian perintah yang perlu dikirim KE Pixhawk (gripper, dll),
# supaya semua penulisan ke serial port dilakukan dari satu thread saja.
outgoing_commands = queue.Queue()

# Kumpulan koneksi WebSocket dashboard yang sedang tersambung.
connected_clients = set()
main_loop = None  # diisi saat asyncio berjalan, dipakai thread MAVLink untuk broadcast


# ============================================================
# THREAD: BACA & TULIS MAVLINK
# ============================================================
def mavlink_worker():
    print(f"[MAVLink] Menyambung ke {config.MAVLINK_CONNECTION} @ {config.MAVLINK_BAUD}...")

    while True:
        try:
            master = mavutil.mavlink_connection(
                config.MAVLINK_CONNECTION, baud=config.MAVLINK_BAUD
            )
            master.wait_heartbeat(timeout=10)
            print("[MAVLink] Heartbeat diterima, Pixhawk terhubung.")
            with state_lock:
                state["connected"] = True

            # Minta Pixhawk mengirim stream data secara berkala.
            master.mav.request_data_stream_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10,  # Hz
                1,   # start
            )

            _mavlink_loop(master)

        except Exception as err:
            print(f"[MAVLink] Terputus/gagal konek: {err}. Coba lagi 3 detik...")
            with state_lock:
                state["connected"] = False
            time.sleep(3)


def _mavlink_loop(master):
    """Loop utama: baca pesan masuk, proses perintah keluar (gripper)."""
    last_heartbeat = time.time()

    while True:
        # --- kirim perintah yang menunggu di antrian (mis. gripper) ---
        try:
            while True:
                cmd = outgoing_commands.get_nowait()
                _send_command(master, cmd)
        except queue.Empty:
            pass

        # --- baca pesan MAVLink masuk (non-blocking) ---
        msg = master.recv_match(blocking=True, timeout=0.2)
        if msg is None:
            if time.time() - last_heartbeat > 5:
                raise ConnectionError("Tidak ada heartbeat > 5 detik")
            continue

        msg_type = msg.get_type()

        if msg_type == "HEARTBEAT":
            last_heartbeat = time.time()
            with state_lock:
                state["connected"] = True

        elif msg_type == "ATTITUDE":
            with state_lock:
                state["pitch"] = math.degrees(msg.pitch)
                state["roll"] = math.degrees(msg.roll)
                state["yaw"] = math.degrees(msg.yaw) % 360

        elif msg_type == "GLOBAL_POSITION_INT" and config.DEPTH_SOURCE == "global_position_int":
            with state_lock:
                # ArduSub: relative_alt negatif di bawah air (mm) -> depth positif dalam meter
                state["depth"] = max(0.0, -msg.relative_alt / 1000.0)

        elif msg_type == "SCALED_PRESSURE2" and config.DEPTH_SOURCE == "baro":
            # Butuh kalibrasi tekanan permukaan (surface_pressure) sendiri.
            # Simpan tekanan mentah dulu; sesuaikan rumus densitas air kalau dipakai.
            pass

        elif msg_type == "SYS_STATUS":
            with state_lock:
                if msg.voltage_battery not in (0, -1, 65535):
                    state["battery"] = msg.voltage_battery / 1000.0

        elif msg_type == "SERVO_OUTPUT_RAW" and config.GRIPPER_MODE == "servo":
            pwm = _get_servo_channel_value(msg, config.GRIPPER_SERVO_CHANNEL)
            if pwm:
                midpoint = (config.GRIPPER_OPEN_PWM + config.GRIPPER_CLOSED_PWM) / 2
                gripper_state = "open" if pwm >= midpoint else "closed"
                with state_lock:
                    if state["gripper"] != gripper_state:
                        state["gripper"] = gripper_state

        # Broadcast state terbaru ke semua dashboard yang tersambung.
        _schedule_broadcast()


def _get_servo_channel_value(msg, channel):
    return getattr(msg, f"servo{channel}_raw", None)


def _send_command(master, cmd):
    if cmd["type"] == "gripper_command" and config.GRIPPER_MODE == "servo":
        pwm = config.GRIPPER_OPEN_PWM if cmd["state"] == "open" else config.GRIPPER_CLOSED_PWM
        print(f"[MAVLink] Set servo channel {config.GRIPPER_SERVO_CHANNEL} -> {pwm} ({cmd['state']})")
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,  # confirmation
            config.GRIPPER_SERVO_CHANNEL,
            pwm,
            0, 0, 0, 0, 0,
        )
        with state_lock:
            state["gripper"] = cmd["state"]


# ============================================================
# GPIO (opsional, kalau GRIPPER_MODE = "gpio")
# ============================================================
_gpio_ready = False


def _ensure_gpio():
    global _gpio_ready
    if _gpio_ready:
        return
    import RPi.GPIO as GPIO  # import di sini supaya tidak wajib terpasang kalau tidak dipakai

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(config.GRIPPER_GPIO_PIN, GPIO.OUT)
    _gpio_ready = True


def _set_gripper_gpio(is_open):
    import RPi.GPIO as GPIO

    _ensure_gpio()
    level = is_open == config.GRIPPER_GPIO_ACTIVE_HIGH
    GPIO.output(config.GRIPPER_GPIO_PIN, GPIO.HIGH if level else GPIO.LOW)


# ============================================================
# LOG QR KE FILE CSV
# ============================================================
def log_qr_detection(data, ts_ms):
    file_exists = os.path.isfile(config.QR_LOG_FILE)
    with open(config.QR_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp_iso", "ts_ms", "data"])
        writer.writerow([datetime.fromtimestamp(ts_ms / 1000).isoformat(), ts_ms, data])


# ============================================================
# WEBSOCKET SERVER (asyncio)
# ============================================================
def _schedule_broadcast():
    """Dipanggil dari thread MAVLink; minta loop asyncio kirim broadcast."""
    if main_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(_broadcast_state(), main_loop)
        except RuntimeError:
            pass


async def _broadcast_state():
    if not connected_clients:
        return
    with state_lock:
        payload = json.dumps({"type": "telemetry", **{k: v for k, v in state.items() if v is not None}})
    stale = []
    for ws in connected_clients:
        try:
            await ws.send(payload)
        except websockets.exceptions.ConnectionClosed:
            stale.append(ws)
    for ws in stale:
        connected_clients.discard(ws)


async def handle_client(websocket):
    print(f"[WS] Dashboard tersambung: {websocket.remote_address}")
    connected_clients.add(websocket)
    try:
        # Kirim state terkini segera setelah dashboard connect.
        with state_lock:
            payload = json.dumps({"type": "telemetry", **{k: v for k, v in state.items() if v is not None}})
        await websocket.send(payload)

        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "gripper_command" and msg.get("state") in ("open", "closed"):
                if config.GRIPPER_MODE == "servo":
                    outgoing_commands.put(msg)
                else:
                    _set_gripper_gpio(msg["state"] == "open")
                    with state_lock:
                        state["gripper"] = msg["state"]

            elif msg.get("type") == "qr_detected" and msg.get("data"):
                print(f"[QR] Terdeteksi: {msg['data']}")
                log_qr_detection(msg["data"], msg.get("ts", int(time.time() * 1000)))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Dashboard terputus: {websocket.remote_address}")


async def periodic_broadcast():
    """Broadcast berkala sebagai jaring pengaman kalau MAVLink lagi sepi pesan."""
    interval = 1.0 / max(1, config.TELEMETRY_SEND_HZ)
    while True:
        await asyncio.sleep(interval)
        await _broadcast_state()


async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()

    threading.Thread(target=mavlink_worker, daemon=True).start()

    async with websockets.serve(handle_client, config.WS_HOST, config.WS_PORT):
        print(f"[WS] Server WebSocket jalan di ws://{config.WS_HOST}:{config.WS_PORT}")
        await periodic_broadcast()


if __name__ == "__main__":
    asyncio.run(main())
