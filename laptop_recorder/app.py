"""Run on the LAPTOP: python -m laptop_recorder.app --pi http://PI-IP:8000"""
import argparse
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from laptop_recorder.camera import RemoteCamera
from laptop_recorder.recording import RECORDINGS_DIR, build_recording_router

ROOT = Path(__file__).resolve().parents[1]


def valid_pi_url(value):
    url = urlsplit(value)
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username
            or url.password or url.query or url.fragment or url.path not in {'', '/'}):
        raise argparse.ArgumentTypeError('Gunakan alamat backend Pi, contoh http://192.168.0.1:8000')
    return value.rstrip('/')


def same_origin(origin, host):
    if origin is None:
        return True
    url = urlsplit(origin)
    return url.scheme == 'http' and url.netloc == host


def create_app(pi_url, output=RECORDINGS_DIR, fps=15, cameras=None):
    pi_url = valid_pi_url(pi_url)
    output = Path(output).expanduser().resolve()
    if cameras is None:
        cameras = {key: RemoteCamera(f'{pi_url}/video/{key}', fps) for key in ('cam1', 'cam2')}
    router, recorders = build_recording_router(cameras, output)

    @asynccontextmanager
    async def lifespan(app):
        for camera in cameras.values():
            camera.start()
        try:
            yield
        finally:
            for recorder in recorders.values():
                await asyncio.to_thread(recorder.stop)
            for camera in cameras.values():
                await asyncio.to_thread(camera.stop)

    app = FastAPI(lifespan=lifespan)
    app.state.recorders = recorders
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]'])
    app.include_router(router)

    @app.middleware('http')
    async def local_origin_only(request, call_next):
        if not same_origin(request.headers.get('origin'), request.headers.get('host')):
            return JSONResponse({'detail': 'Open the local laptop GUI to use this service.'}, status_code=403)
        return await call_next(request)

    @app.get('/api/laptop')
    def laptop_info():
        return dict(pi_url=pi_url, output_directory=str(output), storage='laptop')

    @app.get('/video/latest_qr')
    async def latest_qr():
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                response = await client.get(f'{pi_url}/video/latest_qr')
            return Response(response.content, status_code=response.status_code,
                            media_type=response.headers.get('content-type', 'application/octet-stream'))
        except httpx.HTTPError:
            return JSONResponse({'error': 'Raspberry Pi tidak terhubung.'}, status_code=502)

    @app.get('/video/{camera_id}')
    async def video(camera_id: str):
        if camera_id not in cameras:
            return Response(status_code=404)

        async def frames():
            last_sequence = -1
            while True:
                sequence, jpeg = cameras[camera_id].get_jpeg()
                if jpeg is None:
                    # Close stream after signal loss so the existing GUI reconnects.
                    return
                if sequence != last_sequence:
                    last_sequence = sequence
                    yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n'
                await asyncio.sleep(1 / max(1, fps))

        if cameras[camera_id].get_jpeg()[1] is None:
            return Response(status_code=503)
        return StreamingResponse(frames(), media_type='multipart/x-mixed-replace; boundary=frame',
                                 headers={'Cache-Control': 'no-store'})

    @app.websocket('/ws/telemetry')
    async def telemetry(websocket: WebSocket):
        if not same_origin(websocket.headers.get('origin'), websocket.headers.get('host')):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        upstream_url = ('wss' if pi_url.startswith('https:') else 'ws') + pi_url[pi_url.index(':'):] + '/ws/telemetry'
        try:
            async with connect(upstream_url, open_timeout=3, max_size=2**20, proxy=None) as upstream:
                async def to_pi():
                    while True:
                        await upstream.send(await websocket.receive_text())

                async def to_gui():
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)

                tasks = [asyncio.create_task(to_pi()), asyncio.create_task(to_gui())]
                try:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except (OSError, ConnectionClosed, InvalidHandshake, TimeoutError, WebSocketDisconnect):
            pass
        finally:
            try:
                await websocket.close(code=1011)
            except (RuntimeError, WebSocketDisconnect):
                pass

    @app.get('/')
    async def index():
        return FileResponse(ROOT / 'index.html')

    for name in ('css', 'js', 'assets'):
        app.mount('/' + name, StaticFiles(directory=ROOT / name), name=name)
    return app


def main():
    parser = argparse.ArgumentParser(description='GUI ROV + perekam video ke disk laptop')
    parser.add_argument('--pi', required=True, type=valid_pi_url, help='Alamat backend Raspberry Pi, termasuk port 8000')
    parser.add_argument('--output', type=Path, default=RECORDINGS_DIR, help='Folder video di laptop')
    parser.add_argument('--port', type=int, default=8080, help='Port GUI laptop (default 8080)')
    parser.add_argument('--fps', type=int, default=15, choices=range(1, 31), metavar='1-30')
    args = parser.parse_args()
    print(f'GUI laptop: http://127.0.0.1:{args.port}', flush=True)
    print(f'Video disimpan di laptop: {args.output.expanduser().resolve()}', flush=True)
    print('Biarkan terminal ini berjalan. Tekan Ctrl+C untuk berhenti.', flush=True)
    import uvicorn
    uvicorn.run(create_app(args.pi, args.output, args.fps), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
