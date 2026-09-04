import asyncio
import cv2
import os
import time
try:
    from pyzbar.pyzbar import decode
    USE_PYZBAR = True
except ImportError:
    USE_PYZBAR = False

from backend.camera_stream import cam1

qr_queue = asyncio.Queue()

CAPTURES_DIR = os.path.join(os.path.dirname(__file__), "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

class LatestQRState:
    timestamp = 0
    filepath = None

async def qr_scanner_loop():
    consecutive_reads = 0
    last_payload = None
    debounce_threshold = 3
    
    detector = cv2.QRCodeDetector() if not USE_PYZBAR else None

    while True:
        frame = cam1.get_frame()
        if frame is not None:
            detected_data = None
            if USE_PYZBAR:
                decoded_objects = decode(frame)
                if decoded_objects:
                    detected_data = decoded_objects[0].data.decode("utf-8")
            else:
                data, bbox, _ = detector.detectAndDecode(frame)
                if data:
                    detected_data = data
                    
            if detected_data:
                if detected_data == last_payload:
                    consecutive_reads += 1
                else:
                    last_payload = detected_data
                    consecutive_reads = 1
                
                if consecutive_reads == debounce_threshold:
                    filename = f"qr_{int(time.time())}.jpg"
                    filepath = os.path.join(CAPTURES_DIR, filename)
                    cv2.imwrite(filepath, frame)
                    
                    LatestQRState.timestamp = time.time()
                    LatestQRState.filepath = filepath

                    await qr_queue.put({
                        "type": "qr_detected",
                        "side": "A", 
                        "valid": True,
                        "data": detected_data,
                        "timestamp": LatestQRState.timestamp
                    })
                    consecutive_reads = 0
            else:
                consecutive_reads = 0
                last_payload = None
                
        await asyncio.sleep(0.5)
