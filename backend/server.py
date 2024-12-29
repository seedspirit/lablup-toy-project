import aiohttp
from aiohttp import web
from aiohttp.web import json_response, WebSocketResponse
import redis
import json
import pickle
import asyncio
import logging

from redis.client import PubSub

routes = web.RouteTableDef()
redis_client = redis.Redis()
redis_pubsub_client = redis_client.pubsub()

@routes.get('/')
async def index(request):
    return json_response({"message": "hello this is chat app"}) 

@routes.post('/rooms')
async def create_chat_room(request):
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
async def send_chat(request):
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
async def get_chat(request):
    room_id = request.match_info['room_id']
    room_key = "room:" + room_id
    messages = await redis_client.zrange(name=room_key, start=0, end=-1)
    decoded_message = [pickle.loads(message) for message in messages]
    return json_response({"data": decoded_message})


CHANNEL = "one"
async def handle_redis_messages(websocket: WebSocketResponse, pubsub: PubSub):
        while not websocket.closed:
            message = pubsub.get_message()
            if message and message["type"] == "message":
                try:
                    await websocket.send_json(pickle.loads(message["data"]))
                except:
                    break
            await asyncio.sleep(0.01)

@routes.get('/ws')
async def websocket_connect(request):
    ws = WebSocketResponse()
    await ws.prepare(request)
    pubsub = None

    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe(CHANNEL)
        
        # Redis 구독 처리를 위한 별도 태스크 생성
        asyncio.create_task(handle_redis_messages(ws, pubsub))
        
        # WebSocket 메시지 처리
        while True:
            try:
                msg = await ws.receive()
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close':
                        await ws.close()
                        break
                        
                    data = json.loads(msg.data)
                    chat = {
                        "from": data["user_id"],
                        "date": data["timestamp"],
                        "message": data["message"],
                    }
                    redis_client.publish(CHANNEL, pickle.dumps(chat))
                    
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
                    break
                    
            except Exception as e:
                logging.error(f"Error in WebSocket loop: {e}", exc_info=True)
                break
                
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        if pubsub:
            pubsub.unsubscribe(CHANNEL)
            pubsub.close()
        await ws.close()
        
    return ws

# Infra Layer
def init_redis():
    redis.Redis(host="localhost", port=6379, decode_responses=False)

app = web.Application()
app.router.add_routes(routes=routes)


if __name__ == '__main__':
    init_redis()
    web.run_app(app)