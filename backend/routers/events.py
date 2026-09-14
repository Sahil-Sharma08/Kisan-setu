import json
from typing import Dict, List, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["Real-time Yard & Event Bus"])

class YardConnectionManager:
    """Manages real-time WebSocket connections across Mandi Yard displays, gates, and command desks."""
    def __init__(self):
        # Map center_id -> list of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, center_id: str):
        await websocket.accept()
        cid = center_id.strip().upper()
        if cid not in self.active_connections:
            self.active_connections[cid] = []
        self.active_connections[cid].append(websocket)

    def disconnect(self, websocket: WebSocket, center_id: str):
        cid = center_id.strip().upper()
        if cid in self.active_connections and websocket in self.active_connections[cid]:
            self.active_connections[cid].remove(websocket)

    async def broadcast(self, center_id: str, message: Dict[str, Any]):
        cid = center_id.strip().upper()
        targets = self.active_connections.get(cid, [])
        for conn in list(targets):
            try:
                await conn.send_json(message)
            except Exception:
                if conn in targets:
                    targets.remove(conn)

    async def broadcast_all(self, message: Dict[str, Any]):
        for cid in list(self.active_connections.keys()):
            await self.broadcast(cid, message)

manager = YardConnectionManager()

@router.websocket("/ws/{center_id}")
async def yard_websocket_endpoint(websocket: WebSocket, center_id: str):
    """
    Real-time streaming bus for Mandi Yard Displays, Gate Scanners, and Command Center
    """
    await manager.connect(websocket, center_id)
    try:
        # Send initial handshake
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "centerId": center_id.upper(),
            "message": "Connected to KisanSetu Real-time Yard Event Stream"
        })
        while True:
            # Keep connection alive and accept incoming pings or simulated events
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Echo or broadcast if needed
                if msg.get("action") == "PING":
                    await websocket.send_json({"type": "PONG", "timestamp": msg.get("timestamp")})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, center_id)
    except Exception:
        manager.disconnect(websocket, center_id)

async def emit_yard_event(center_id: str, event_type: str, data: Dict[str, Any]):
    """Helper to dispatch reactive events across all connected screens."""
    payload = {
        "type": event_type,
        "centerId": center_id.upper(),
        "data": data
    }
    await manager.broadcast(center_id, payload)
