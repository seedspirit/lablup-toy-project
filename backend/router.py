from pathlib import Path
import uuid, logging

from aiohttp import web
from aiohttp.web import json_response, WebSocketResponse, Request, Response, FileResponse, HTTPException

import aiohttp_session
from aiohttp_session import Session
from aiohttp_session.redis_storage import RedisStorage

from redis_service import RedisService

routes = web.RouteTableDef()

DI_CONTAINER_NAME = 'container'

@routes.get('/')
async def index(request: Request) -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent.parent / 'frontend' / 'view.html')

@routes.get('/session')
async def get_session(request: Request) -> Response:
    session: Session = await aiohttp_session.get_session(request=request)
    session_id = session.get('session_id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        session.changed()
        
    response: Response = json_response({"sessionId": session_id})
    session_storage: RedisStorage = request.app[DI_CONTAINER_NAME].redis_storage
    await session_storage.save_session(request=request, response=response, session=session)

    return response

@routes.get('/ws')
async def websocket_connect(request: Request) -> WebSocketResponse:
    ws: WebSocketResponse = WebSocketResponse()
    try:
        await ws.prepare(request)
    except HTTPException as e:
        logging.error(f"WebSocket connection error: {e}", exc_info=True)
        return ws

    request.app['active_websockets'].add(ws)

    # RedisService내에서 무한루프를 돌며 채팅 메시지 pub/sub
    redis_service: RedisService = request.app[DI_CONTAINER_NAME].redis_service
    await redis_service.handle_chat_communication(websocket=ws, channel_name="chat")

    # 연결 종료 시 active_websockets에서 제거
    request.app['active_websockets'].discard(ws)
    await ws.close()
            
    return ws