import asyncio
import math
import time
from pymavlink import mavutil
from backend import config
from backend.qr_scanner import qr_queue

telemetry_state = {
    "depth": 0.0,
    "pitch": 0.0,
    "roll": 0.0,
    "yaw": 0.0,
    "battery": 0.0,
    "connected": False,
    "gripper": "closed"
}
last_heartbeat_time = 0

async def mavlink_listener():
    global last_heartbeat_time
    connection_str = f"udpin:127.0.0.1:{config.LOCAL_TELEMETRY_UDP_PORT}"
    
    while True:
        try:
            master = mavutil.mavlink_connection(connection_str)
            while True:
                msg = master.recv_match(blocking=False)
                if not msg:
                    await asyncio.sleep(0.01)
                    continue
                
                msg_type = msg.get_type()
                if msg_type == "HEARTBEAT":
                    last_heartbeat_time = time.time()
                elif msg_type == "ATTITUDE":
                    telemetry_state["pitch"] = math.degrees(msg.pitch)
                    telemetry_state["roll"] = math.degrees(msg.roll)
                    telemetry_state["yaw"] = math.degrees(msg.yaw) % 360
                elif msg_type == "SYS_STATUS":
                    if msg.voltage_battery not in (0, -1, 65535):
                        telemetry_state["battery"] = msg.voltage_battery / 1000.0
                elif msg_type == "SERVO_OUTPUT_RAW":
                    pwm = getattr(msg, f"servo{config.GRIPPER_SERVO_CHANNEL}_raw", None)
                    if pwm is not None:
                        midpoint = (config.GRIPPER_PWM_OPEN + config.GRIPPER_PWM_CLOSED) / 2
                        telemetry_state["gripper"] = "open" if pwm >= midpoint else "closed"
                
                if config.DEPTH_SOURCE == "pressure" and msg_type == "SCALED_PRESSURE2":
                    pass # Custom scaling for pressure
                elif config.DEPTH_SOURCE == "rangefinder" and msg_type == "DISTANCE_SENSOR":
                    telemetry_state["depth"] = msg.current_distance / 100.0
                elif msg_type == "GLOBAL_POSITION_INT":
                    telemetry_state["depth"] = max(0.0, -msg.relative_alt / 1000.0)

        except Exception as e:
            print(f"MAVLink bridge error: {e}. Retrying in 2s...")
            await asyncio.sleep(2)

async def websocket_handler(websocket):
    await websocket.accept()
    interval = 1.0 / config.TELEMETRY_HZ
    
    async def send_telemetry():
        while True:
            telemetry_state["connected"] = (time.time() - last_heartbeat_time) <= 3.0
            await websocket.send_json({
                "type": "telemetry",
                **telemetry_state
            })
            await asyncio.sleep(interval)
            
    async def send_qr():
        while True:
            qr_msg = await qr_queue.get()
            await websocket.send_json(qr_msg)
            
    async def receive_commands():
        while True:
            try:
                data = await websocket.receive_json()
                pass # Forward commands here if needed later
            except Exception:
                break
                
    try:
        await asyncio.gather(send_telemetry(), send_qr(), receive_commands())
    except Exception:
        pass
