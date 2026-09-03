import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend import config
from backend.camera_stream import get_cam1_stream, get_cam2_stream
from backend.qr_scanner import qr_scanner_loop
from backend.mavlink_bridge import mavlink_listener, websocket_handler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(mavlink_listener())
    asyncio.create_task(qr_scanner_loop())

@app.get("/video/cam1")
async def video_cam1():
    return get_cam1_stream()

@app.get("/video/cam2")
async def video_cam2():
    return get_cam2_stream()

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket_handler(websocket)

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

if __name__ == "__main__":
    uvicorn.run("backend.run_backend:app", host="0.0.0.0", port=config.HTTP_PORT, reload=False)
