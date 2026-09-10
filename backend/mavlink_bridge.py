import asyncio
import math
import time
from pymavlink import mavutil
from backend import config
from backend.stop_control import StopControl

stop_control = StopControl(mavutil.mavlink)
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
position_state = {
    "x": 0.0,
    "y": 0.0
}
last_heartbeat_time = 0
last_calc_time = time.time()
has_local_pos = False

async def mavlink_listener():
    global last_heartbeat_time, last_calc_time, has_local_pos
    connection_str = f"udpin:127.0.0.1:{config.LOCAL_TELEMETRY_UDP_PORT}"
    
    while True:
        try:
            master = mavutil.mavlink_connection(
                connection_str, source_system=config.STOP_SOURCE_SYSTEM,
                source_component=config.STOP_SOURCE_COMPONENT)
            stop_control.attach(master)
            last_calc_time = time.time()
            while True:
                stop_control.tick()
                msg = master.recv_match(blocking=False)
                if not msg:
                    await asyncio.sleep(0.01)
                    continue
                
                stop_control.observe(msg)
                if (msg.get_srcSystem(), msg.get_srcComponent()) != stop_control.target:
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
                
                elif msg_type == "LOCAL_POSITION_NED":
                    position_state["x"] = msg.x
                    position_state["y"] = msg.y
                    has_local_pos = True
                elif msg_type == "RC_CHANNELS" and not has_local_pos:
                    # Estimate dead reckoning using RC input (chan5=forward, chan6=lateral) + Yaw
                    forward_pwm = msg.chan5_raw
                    lateral_pwm = msg.chan6_raw
                    
                    # Prevent bad values
                    if 1100 <= forward_pwm <= 1900 and 1100 <= lateral_pwm <= 1900:
                        forward = max(-1.0, min(1.0, (forward_pwm - 1500) / 400.0))
                        lateral = max(-1.0, min(1.0, (lateral_pwm - 1500) / 400.0))
                        
                        now = time.time()
                        dt = now - last_calc_time
                        last_calc_time = now
                        
                        if dt > 0 and dt < 1.0: # ignore large jumps
                            yaw_rad = math.radians(telemetry_state["yaw"])
                            speed = getattr(config, 'DR_MAX_SPEED_MPS', 0.6)
                            
                            vx = (forward * math.sin(yaw_rad) + lateral * math.cos(yaw_rad)) * speed
                            vy = (-forward * math.cos(yaw_rad) + lateral * math.sin(yaw_rad)) * speed
                            
                            position_state["x"] += vx * dt
                            position_state["y"] += vy * dt
                    else:
                        last_calc_time = time.time()

        except Exception as e:
            stop_control.disconnect()
            print(f"MAVLink bridge error: {e}. Retrying in 2s...")
            await asyncio.sleep(2)
        finally:
            stop_control.disconnect()
            if "master" in locals():
                master.close()

async def websocket_handler(websocket):
    await websocket.accept()
    interval = 1.0 / config.TELEMETRY_HZ
    send_lock = asyncio.Lock()

    async def send_json(payload):
        async with send_lock:
            await websocket.send_json(payload)
    
    async def send_telemetry():
        while True:
            safety = stop_control.telemetry()
            telemetry_state["connected"] = safety["connected"]
            await send_json({
                "type": "telemetry",
                **telemetry_state,
                **safety
            })
            # Also send position data
            await send_json({
                "type": "position",
                "x": position_state["x"],
                "y": position_state["y"]
            })
            await asyncio.sleep(interval)
            
    async def send_qr():
        while True:
            qr_msg = await qr_queue.get()
            await send_json(qr_msg)
            
    async def receive_commands():
        while True:
            try:
                data = await websocket.receive_json()
                if not isinstance(data, dict):
                    await send_json({"type": "command_result", "error": "Perintah tidak valid."})
                    continue
                if data.get("type") == "command" and data.get("command") == "disarm":
                    result = stop_control.request(data.get("id"))
                    await send_json({"type": "command_result", "id": data.get("id"), **result})
                else:
                    await send_json({"type": "command_result", "id": data.get("id"),
                                     "error": "Perintah tidak didukung."})
            except Exception:
                break
                
    tasks = [asyncio.create_task(fn()) for fn in (send_telemetry, send_qr, receive_commands)]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
