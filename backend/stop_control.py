"""Normal DISARM only; completion is observed from a fresh FC heartbeat.

This is a software stop request, not an electrical emergency cutoff.
The listener and WebSocket handler run on the same asyncio event loop.
"""
import time


class StopControl:
    HEARTBEAT_TIMEOUT = 3.0
    COMMAND_TIMEOUT = 5.0
    RETRY_INTERVAL = 1.0
    MAX_SENDS = 3

    def __init__(self, protocol, clock=time.monotonic):
        self.p = protocol
        self.clock = clock
        self.connection = None
        self.target = None
        self.last_heartbeat = None
        self.armed = None
        self.status = {"id": None, "phase": "idle", "message": "Belum ada permintaan DISARM."}
        self.sent = 0
        self.acknowledged = False

    def attach(self, connection):
        self.disconnect()
        self.connection = connection

    def disconnect(self):
        if self.status["phase"] == "pending":
            self._finish("unconfirmed", "Koneksi putus; DISARM belum terkonfirmasi.")
        self.connection = None
        self.target = None
        self.last_heartbeat = None
        self.armed = None

    def fresh(self):
        return (self.connection is not None and self.last_heartbeat is not None
                and self.clock() - self.last_heartbeat < self.HEARTBEAT_TIMEOUT)

    def observe(self, msg):
        source = (msg.get_srcSystem(), msg.get_srcComponent())
        kind = msg.get_type()
        if kind == "HEARTBEAT":
            # Only this ROV's autopilot may establish the command target.
            if (msg.type != self.p.MAV_TYPE_SUBMARINE
                    or msg.autopilot != self.p.MAV_AUTOPILOT_ARDUPILOTMEGA
                    or source[1] != self.p.MAV_COMP_ID_AUTOPILOT1
                    or source[0] == 0):
                return
            if self.target is not None and source != self.target:
                return
            self.target = source
            self.last_heartbeat = self.clock()
            self.armed = bool(msg.base_mode & self.p.MAV_MODE_FLAG_SAFETY_ARMED)
            if self.status["phase"] == "pending" and not self.armed:
                self._finish("confirmed", "Pixhawk melaporkan DISARM.")
        elif (kind == "COMMAND_ACK" and source == self.target
              and self.status["phase"] == "pending"
              and msg.command == self.p.MAV_CMD_COMPONENT_ARM_DISARM):
            # MAVLink 2 ACK recipient fields; MAVLink 1 has no recipient fields.
            if (getattr(msg, "target_system", 0) not in (0, self.connection.source_system)
                    or getattr(msg, "target_component", 0) not in
                    (0, self.connection.source_component)):
                return
            if msg.result in (self.p.MAV_RESULT_ACCEPTED, self.p.MAV_RESULT_IN_PROGRESS):
                self.acknowledged = True
                self.status["message"] = "Perintah diterima; menunggu heartbeat DISARM."
            else:
                self._finish("rejected", f"Pixhawk menolak DISARM (kode {msg.result}).")

    def request(self, request_id):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 80:
            return {"error": "ID permintaan tidak valid."}
        self.tick()
        if self.status["phase"] == "pending":
            return {"error": "Permintaan DISARM sedang diproses.", "stop": self.snapshot()}
        if self.status["id"] == request_id:
            return {"stop": self.snapshot()}
        self.status = {"id": request_id, "phase": "pending", "message": "Mengirim DISARM…"}
        self.sent = 0
        self.acknowledged = False
        self.deadline = self.clock() + self.COMMAND_TIMEOUT
        if not self.fresh():
            self._finish("unconfirmed", "Heartbeat Pixhawk tidak tersedia; perintah tidak dikirim.")
        elif self.armed is False:
            self._finish("confirmed", "Pixhawk sudah DISARM berdasarkan heartbeat terbaru.")
        else:
            self._send()
        return {"stop": self.snapshot()}

    def _send(self):
        try:
            self.connection.mav.command_long_send(
                *self.target, self.p.MAV_CMD_COMPONENT_ARM_DISARM,
                self.sent, 0, 0, 0, 0, 0, 0, 0,
            )
            # param1=0 (DISARM), param2=0 (respect FC safety checks).
            self.sent += 1
            self.last_send = self.clock()
            self.status["message"] = "DISARM dikirim; menunggu konfirmasi Pixhawk."
        except Exception:
            self._finish("unconfirmed", "Gagal mengirim; DISARM belum terkonfirmasi.")

    def tick(self):
        if self.status["phase"] != "pending":
            return
        if not self.fresh():
            self._finish("unconfirmed", "Heartbeat hilang; DISARM belum terkonfirmasi.")
        elif self.clock() >= self.deadline:
            self._finish("unconfirmed", "Waktu tunggu habis; DISARM belum terkonfirmasi.")
        elif (not self.acknowledged and self.sent < self.MAX_SENDS
              and self.clock() - self.last_send >= self.RETRY_INTERVAL):
            self._send()

    def _finish(self, phase, message):
        self.status.update(phase=phase, message=message)

    def snapshot(self):
        return dict(self.status)

    def telemetry(self):
        self.tick()
        fresh = self.fresh()
        return {"connected": fresh, "armed": self.armed if fresh else None,
                "stop_available": fresh, "stop": self.snapshot()}
