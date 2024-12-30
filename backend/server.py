import uuid
import aiohttp
from aiohttp import web
from aiohttp.web import json_response, WebSocketResponse, Request, Response, FileResponse

import aiohttp_session
from aiohttp_session.redis_storage import RedisStorage
from aiohttp_session import Session

import redis
from redis.client import PubSub
from redis import asyncio as aioredis

import json
import pickle
import asyncio
import logging
from pathlib import Path


routes = web.RouteTableDef()
redis_client = redis.Redis()
redis_pubsub_client = redis_client.pubsub()

COOKIE_NAME = "aiohttp_chat_app_session_id"
ONE_HOUR = 60 * 60
session_storage = RedisStorage(aioredis.Redis(), cookie_name=COOKIE_NAME, max_age=ONE_HOUR)

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / 'frontend' / 'view.html'

@routes.get('/')
async def index(request: Request) -> FileResponse:
    return FileResponse(INDEX_HTML_PATH)

@routes.get('/session')
async def get_session(request: Request) -> Response:
    session: Session = await aiohttp_session.get_session(request=request)
    session_id = session.get('session_id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        session.changed()
        
    response: Response = json_response({"sessionId": session_id})
    await session_storage.save_session(request=request, response=response, session=session)
    return response

CHANNEL = "one"

PUBSUB_FIELD_TYPE = "type"
PUBSUB_FIELD_DATA = "data"
PUBSUB_TYPE_MESSAGE = "message"

async def receive_chat_message(websocket: WebSocketResponse, pubsub: PubSub) -> None:
    while not websocket.closed:
        message = pubsub.get_message()
        if message and message[PUBSUB_FIELD_TYPE] == PUBSUB_TYPE_MESSAGE:
            try:
                await websocket.send_json(pickle.loads(message[PUBSUB_FIELD_DATA]))
            except:
                break
        await asyncio.sleep(0.01)

async def publish_chat_message(websocket: WebSocketResponse) -> None:
    while not websocket.closed:
        try:   
            msg = await websocket.receive() 

            if msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
                break

            data = json.loads(msg.data)
            chat = {
                "from": data["user_id"],
                "date": data["timestamp"],
                "message": data["message"],
            }
            redis_client.publish(CHANNEL, pickle.dumps(chat))

        except Exception as e:
            logging.error(f"Error in WebSocket loop: {e}", exc_info=True)
            break

@routes.get('/ws')
async def websocket_connect(request: Request) -> WebSocketResponse:
    ws: WebSocketResponse = WebSocketResponse()
    await ws.prepare(request)
    
    with redis_client.pubsub() as pubsub:
        try:
            pubsub.subscribe(CHANNEL)
            
            receive_task: asyncio.Task = asyncio.create_task(receive_chat_message(websocket=ws, pubsub=pubsub))
            publish_task: asyncio.Task = asyncio.create_task(publish_chat_message(websocket=ws))

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
            pubsub.unsubscribe(CHANNEL)
            await ws.close()
            
    return ws

# Infra Layer
def init_redis():
    redis.Redis(host="localhost", port=6379, decode_responses=False)

app = web.Application()
app.router.add_routes(routes=routes)
aiohttp_session.setup(app, session_storage)

if __name__ == '__main__':
    init_redis()
    web.run_app(app)