# endpoints/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import json

api_router = APIRouter(tags=["WebSocket"])

active_connections: Dict[str, Dict[str, WebSocket]] = {}


class ConnectionManager:
    def connect(self, websocket: WebSocket, access_code: str, student_id: str):
        """Просто сохраняем подключение (accept уже вызван в endpoint)"""
        if access_code not in active_connections:
            active_connections[access_code] = {}

        active_connections[access_code][student_id] = websocket
        print(f"✅ Client {student_id} connected to session {access_code}")

    def disconnect(self, access_code: str, student_id: str):
        if access_code in active_connections:
            active_connections[access_code].pop(student_id, None)
            print(f"❌ Client {student_id} disconnected from session {access_code}")

            if not active_connections[access_code]:
                del active_connections[access_code]

    async def broadcast_to_session(self, access_code: str, message: dict, exclude: str = None):
        """Отправить сообщение всем участникам сессии"""
        if access_code not in active_connections:
            return

        disconnected = []
        for student_id, websocket in active_connections[access_code].items():
            if student_id == exclude:
                continue
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"Error sending to {student_id}: {e}")
                disconnected.append(student_id)

        for student_id in disconnected:
            self.disconnect(access_code, student_id)

    async def send_personal_message(self, access_code: str, student_id: str, message: dict):
        """Отправить личное сообщение"""
        if access_code in active_connections and student_id in active_connections[access_code]:
            try:
                await active_connections[access_code][student_id].send_json(message)
            except Exception as e:
                print(f"Error sending personal message: {e}")
                self.disconnect(access_code, student_id)


manager = ConnectionManager()


@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint для live-сессий
    """
    await websocket.accept()  # ✅ ОДИН РАЗ здесь!
    print("🔌 WebSocket connection accepted")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            event = message.get("event")
            payload = message.get("payload", {})

            print(f"📥 Received event: {event}")

            if event == "session:join":
                access_code = payload.get("access_code")
                student_id = payload.get("student_id")

                if not access_code or not student_id:
                    await websocket.send_json({
                        "event": "error",
                        "payload": {"message": "Missing access_code or student_id"}
                    })
                    continue

                # Сохраняем подключение (без accept!)
                manager.connect(websocket, access_code, student_id)

                # Отправляем подтверждение
                await manager.send_personal_message(access_code, student_id, {
                    "event": "session:joined",
                    "payload": {
                        "session_id": access_code,
                        "message": "Successfully joined session"
                    }
                })

                # Рассылаем всем о новом участнике
                await manager.broadcast_to_session(access_code, {
                    "event": "session:participant_joined",
                    "payload": {
                        "student_id": student_id,
                        "count": len(active_connections.get(access_code, {}))
                    }
                }, exclude=student_id)

            elif event == "session:leave":
                access_code = payload.get("access_code")
                student_id = payload.get("student_id")

                if access_code and student_id:
                    manager.disconnect(access_code, student_id)

                    await manager.broadcast_to_session(access_code, {
                        "event": "session:participant_left",
                        "payload": {
                            "student_id": student_id,
                            "count": len(active_connections.get(access_code, {}))
                        }
                    })

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")