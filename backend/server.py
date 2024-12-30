import uuid
import aiohttp
from aiohttp import web
from aiohttp.web import json_response, WebSocketResponse, Request, Response, FileResponse

import aiohttp_session
import aiohttp_session.redis_storage as redis_storage
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
session_storage = redis_storage.RedisStorage(aioredis.Redis())

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / 'frontend' / 'view.html'

@routes.get('/')
async def index(request: Request) -> FileResponse:
    return FileResponse(INDEX_HTML_PATH)

@routes.post('/rooms')
async def create_chat_room(request) -> Response:
    data = await request.json()
    user1_id = data["user1_id"]
    user2_id = data["user2_id"]
    room_key: str = f"room:{user1_id}:{user2_id}"
    if redis_client.sismember(name=f"user:{user1_id}:rooms", value=room_key): 
        return json_response({"error": f"room for {user1_id}, {user2_id} already exists"}, status=400)
    
    redis_client.sadd(f"user:{user1_id}:rooms", room_key)
    redis_client.sadd(f"user:{user2_id}:rooms", room_key)

    return json_response({"id": f"{user1_id}:{user2_id}"})

# TODO: 채팅방에 참여한 유저가 아닌데 메시지를 보내는 경우 에러처리
@routes.post('/rooms/{room_id}/chat')
async def send_chat(request: Request) -> Response:
    room_id = request.match_info['room_id']
    room_key = "room:" + room_id  
    data = await request.json()
    user_id = data["user_id"]
    message = data["message"]
    timestamp = data["timestamp"]
    chat = {
        "from": user_id,
        "date": timestamp,
        "message": message,
        "room_id": room_id
    }
    redis_client.zadd(name=room_key, mapping={pickle.dumps(chat): int(timestamp)})
    return json_response(chat)

@routes.get('/rooms/{room_id}/chat')
async def get_chat(request: Request) -> Response:
    room_id = request.match_info['room_id']
    room_key = "room:" + room_id
    messages = await redis_client.zrange(name=room_key, start=0, end=-1)
    decoded_message = [pickle.loads(message) for message in messages]
    return json_response({"data": decoded_message})

@routes.get('/session')
async def get_session(request: Request) -> Response:
    session: Session = await aiohttp_session.get_session(request=request)
    session_id = session.get('session_id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        session.changed()
        
    response = json_response({"sessionId": session_id})
    await session_storage.save_session(request=request, response=response, session=session)
    return response

CHANNEL = "one"

PUBSUB_FIELD_TYPE = "type"
PUBSUB_FIELD_DATA = "data"
PUBSUB_TYPE_MESSAGE = "message"

async def receive_chat_messages(websocket: WebSocketResponse, pubsub: PubSub) -> None:
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
            
            receive_task: asyncio.Task = asyncio.create_task(receive_chat_messages(websocket=ws, pubsub=pubsub))
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