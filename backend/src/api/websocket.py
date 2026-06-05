from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_connections: dict[str, list[WebSocket]] = {}


async def broadcast_run_status(run_id: str, status: str) -> None:
    """Send status update to all clients watching a run."""
    for ws in _connections.get(run_id, []):
        try:
            await ws.send_json({"run_id": run_id, "status": status})
        except Exception:
            pass


@router.websocket("/ws/v1/runs/{run_id}")
async def watch_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    _connections.setdefault(run_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        _connections[run_id].remove(websocket)
