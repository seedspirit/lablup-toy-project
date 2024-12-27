from aiohttp import web
from aiohttp.web import json_response 
import redis
import json
import pickle

routes = web.RouteTableDef()
redis_client = redis.Redis()

@routes.get('/')
async def index(request):
    return json_response({"data": "hello world"})

@routes.post('/redis')
async def post_redis(request):
    data = await request.json()
    redis_key = data["key"]
    redis_val = data["value"]
    redis_client.set(redis_key, redis_val)
    return json_response({"data": f"key:{redis_key}, value:{redis_val} stored successfully"})

@routes.get('/redis')
async def get_redis(request):
    key: str = request.rel_url.query.get('key')
    if key is None:
        return json_response({"error": "Query Paramerer 'key' is needed"}, status=400)
    val = redis_client.get(key)
    if val is None:
        return json_response({"error": f"Data of {key} is not found"}, status=404)
    return json_response({"data":val}) 

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
    messages: list[dict[str, str]] = redis_client.zrange(name=room_key, start=0, end=-1)
    decoded_message = [pickle.loads(message) for message in messages]
    return json_response({"data": decoded_message})


# Infra Layer
def init_redis():
    redis.Redis(host="localhost", port=6379, decode_responses=False)

app = web.Application()
app.router.add_routes(routes=routes)


if __name__ == '__main__':
    init_redis()
    web.run_app(app)