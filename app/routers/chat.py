import os
import uuid
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
from app.routers.pages import get_current_user

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "chat")
ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO = {"video/mp4", "video/webm", "video/quicktime"}
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB

router = APIRouter(prefix="/api/chat", tags=["chat"])


class _ConnectionManager:
    def __init__(self):
        self.rooms: Dict[int, List[WebSocket]] = {}

    async def connect(self, ws: WebSocket, room_id: int):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)

    def disconnect(self, ws: WebSocket, room_id: int):
        room = self.rooms.get(room_id, [])
        if ws in room:
            room.remove(ws)

    async def broadcast(self, room_id: int, data: dict):
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = _ConnectionManager()


@router.get("/room")
def get_or_create_room(request: Request, category: str = Query(default="일반문의")):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login_required"}, status_code=401)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM chat_rooms WHERE user_id = :uid AND category = :cat"),
            {"uid": user["id"], "cat": category},
        ).fetchone()
        if row:
            room_id = row.id
        else:
            result = conn.execute(
                text("INSERT INTO chat_rooms (user_id, user_name, category) VALUES (:uid, :name, :cat) RETURNING id"),
                {"uid": user["id"], "name": user["name"], "cat": category},
            )
            conn.commit()
            room_id = result.fetchone().id
    return {"room_id": room_id, "category": category}


@router.get("/my-rooms")
def list_my_rooms(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login_required"}, status_code=401)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT r.id, r.category, r.last_message_at,
                   (SELECT message FROM chat_messages
                    WHERE room_id = r.id ORDER BY created_at DESC LIMIT 1) AS last_msg,
                   (SELECT COUNT(*) FROM chat_messages
                    WHERE room_id = r.id AND sender = 'admin' AND is_read = 0) AS unread
            FROM chat_rooms r
            WHERE r.user_id = :uid
            ORDER BY r.last_message_at DESC
        """), {"uid": user["id"]}).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        if d["last_message_at"]:
            d["last_message_at"] = d["last_message_at"].strftime("%m.%d %H:%M")
        result.append(d)
    return result


@router.get("/rooms")
def list_rooms(request: Request):
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT r.id, r.user_id, r.user_name, r.category, r.last_message_at,
                   (SELECT message FROM chat_messages
                    WHERE room_id = r.id ORDER BY created_at DESC LIMIT 1) AS last_msg,
                   (SELECT COUNT(*) FROM chat_messages
                    WHERE room_id = r.id AND sender = 'user' AND is_read = 0) AS unread
            FROM chat_rooms r
            ORDER BY r.last_message_at DESC
        """)).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        if d["last_message_at"]:
            d["last_message_at"] = d["last_message_at"].strftime("%m.%d %H:%M")
        result.append(d)
    return result


@router.get("/room/{room_id}/messages")
def get_messages(room_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login_required"}, status_code=401)
    is_admin = user.get("role") == "admin"
    with engine.connect() as conn:
        if not is_admin:
            row = conn.execute(
                text("SELECT id FROM chat_rooms WHERE id = :rid AND user_id = :uid"),
                {"rid": room_id, "uid": user["id"]},
            ).fetchone()
            if not row:
                return JSONResponse({"error": "forbidden"}, status_code=403)
        rows = conn.execute(
            text("SELECT id, sender, message, message_type, is_read, created_at FROM chat_messages WHERE room_id = :rid ORDER BY created_at ASC"),
            {"rid": room_id},
        ).fetchall()
        # 읽음 처리: 관리자가 열면 유저 메시지, 유저가 열면 관리자 메시지를 읽음으로
        mark_sender = "user" if is_admin else "admin"
        conn.execute(
            text("UPDATE chat_messages SET is_read=1 WHERE room_id=:rid AND sender=:s AND is_read=0"),
            {"rid": room_id, "s": mark_sender},
        )
        conn.commit()
    # 읽음 처리 후 WebSocket으로 상대방에게 read_receipt 전송
    import asyncio
    asyncio.create_task(_broadcast_read(room_id)) if False else None  # noqa — handled below
    return [
        {
            "sender": r.sender,
            "message": r.message,
            "msg_type": r.message_type or "text",
            "is_read": bool(r.is_read),
            "created_at": r.created_at.strftime("%H:%M") if r.created_at else "",
        }
        for r in rows
    ]


@router.post("/room/{room_id}/read")
async def mark_read(room_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login_required"}, status_code=401)
    is_admin = user.get("role") == "admin"
    mark_sender = "user" if is_admin else "admin"
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE chat_messages SET is_read=1 WHERE room_id=:rid AND sender=:s AND is_read=0"),
            {"rid": room_id, "s": mark_sender},
        )
        conn.commit()
    reader = "admin" if is_admin else "user"
    await manager.broadcast(room_id, {"type": "read_receipt", "reader": reader})
    return {"success": True}


@router.get("/unread")
def get_unread(request: Request):
    user = get_current_user(request)
    if not user:
        return {"count": 0}
    with engine.connect() as conn:
        if user.get("role") == "admin":
            count = conn.execute(
                text("SELECT COUNT(*) FROM chat_messages WHERE sender='user' AND is_read=0")
            ).scalar() or 0
            rooms = conn.execute(
                text("SELECT COUNT(DISTINCT room_id) FROM chat_messages WHERE sender='user' AND is_read=0")
            ).scalar() or 0
            return {"count": int(count), "rooms": int(rooms)}
        else:
            count = conn.execute(
                text("""SELECT COUNT(*) FROM chat_messages cm
                        JOIN chat_rooms cr ON cm.room_id = cr.id
                        WHERE cr.user_id=:uid AND cm.sender='admin' AND cm.is_read=0"""),
                {"uid": user["id"]},
            ).scalar() or 0
    return {"count": int(count)}


@router.post("/room/{room_id}/upload")
async def upload_file(room_id: int, request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "login_required"}, status_code=401)
    content_type = file.content_type or ""
    if content_type in ALLOWED_IMAGE:
        msg_type = "image"
    elif content_type in ALLOWED_VIDEO:
        msg_type = "video"
    else:
        return JSONResponse({"error": "unsupported_type"}, status_code=400)
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        return JSONResponse({"error": "too_large"}, status_code=400)
    ext = os.path.splitext(file.filename or "")[1] or (".jpg" if msg_type == "image" else ".mp4")
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    url = f"/static/uploads/chat/{filename}"
    return {"url": url, "type": msg_type}


@router.websocket("/ws/{room_id}")
async def chat_ws(websocket: WebSocket, room_id: int):
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_json()
            sender = data.get("sender", "user")
            message = (data.get("message") or "").strip()
            msg_type = data.get("msg_type", "text")
            if not message:
                continue
            now = datetime.now()
            with engine.connect() as conn:
                conn.execute(
                    text("INSERT INTO chat_messages (room_id, sender, message, message_type) VALUES (:rid, :s, :m, :mt)"),
                    {"rid": room_id, "s": sender, "m": message, "mt": msg_type},
                )
                conn.execute(
                    text("UPDATE chat_rooms SET last_message_at = :t WHERE id = :rid"),
                    {"t": now, "rid": room_id},
                )
                conn.commit()
            await manager.broadcast(room_id, {
                "type": "message",
                "sender": sender,
                "message": message,
                "msg_type": msg_type,
                "is_read": False,
                "created_at": now.strftime("%H:%M"),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
