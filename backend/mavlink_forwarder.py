import argparse
import sys
import time
from pymavlink import mavutil

# Example systemd unit (mavlink-forwarder.service):
# [Unit]
# Description=MAVLink Forwarder for ROV
# After=network.target
# 
# [Service]
# ExecStart=/usr/bin/python3 /path/to/backend/mavlink_forwarder.py --master /dev/ttyACM0 --baud 115200 --out udp:192.168.1.100:14550 --out udp:127.0.0.1:14551
# Restart=always
# RestartSec=3
# 
# [Install]
# WantedBy=multi-user.target

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", required=True)
    parser.add_argument("--baud", type=int, required=True)
    parser.add_argument("--out", action="append", required=True, help="udp:IP:PORT")
    args = parser.parse_args()

    while True:
        try:
            print(f"Connecting to {args.master} at {args.baud} baud...")
            master = mavutil.mavlink_connection(args.master, baud=args.baud)
            
            outs = []
            for out_str in args.out:
                outs.append(mavutil.mavlink_connection(out_str, input=False))

            print("Connected. Forwarding...")
            last_heartbeat = time.time()
            
            while True:
                msg = master.recv_msg()
                if msg:
                    if msg.get_type() == 'HEARTBEAT':
                        last_heartbeat = time.time()
                    for out in outs:
                        out.write(msg.get_msgbuf())
                
                for out in outs:
                    try:
                        out_msg = out.recv_msg()
                        if out_msg:
                            master.write(out_msg.get_msgbuf())
                    except Exception:
                        pass
                
                if time.time() - last_heartbeat > 3.0:
                    print("WARNING: No HEARTBEAT from FC for >3s!", file=sys.stderr)
                    last_heartbeat = time.time() # suppress rapid spam
                    
                time.sleep(0.001)

        except Exception as e:
            print(f"Error: {e}. Reconnecting in 3 seconds...")
            time.sleep(3)

if __name__ == "__main__":
    main()
