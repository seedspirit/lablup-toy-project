from pathlib import Path
import asyncio, uuid, logging

from aiohttp import web
from aiohttp.web import json_response, WebSocketResponse, Request, Response, FileResponse

import aiohttp_session
from aiohttp_session import Session
from aiohttp_session.redis_storage import RedisStorage

from redis.client import PubSub

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
    await ws.prepare(request)
    request.app['active_websockets'].add(ws)

    redis_service: RedisService = request.app[DI_CONTAINER_NAME].redis_service
    pubsub: PubSub = redis_service.create_pubsub()
    CHANNEL_NAME = "chat"

    try:
        redis_service.subscribe(channel_name=CHANNEL_NAME, pubsub=pubsub)
        
        receive_task: asyncio.Task = asyncio.create_task(
            redis_service.receive_chat_message(websocket=ws, pubsub=pubsub)
        )

        publish_task: asyncio.Task = asyncio.create_task(
            redis_service.publish_chat_message(
                websocket=ws,
                channel_name=CHANNEL_NAME
            )
        )

        # 두 태스크 모두 ws이 close되거나 에러가 발생할 때까지 무한 루프로 실행된다
        done, pending = await asyncio.wait(
            [receive_task, publish_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 둘 중 하나가 에러 혹은 ws close로 완료되면 나머지 태스크도 정리
        for task in pending:
            task.cancel()

    except Exception as e:
        logging.error(f"WebSocket connection error: {e}", exc_info=True)
    
    finally:
        redis_service.unsubscribe(channel_name=CHANNEL_NAME, pubsub=pubsub)
        redis_service.pubsub_close(pubsub=pubsub)

        request.app['active_websockets'].discard(ws)

        await ws.close()
            
    return ws