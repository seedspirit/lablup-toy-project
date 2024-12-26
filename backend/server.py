from aiohttp import web
from aiohttp.web import json_response 
import redis

routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
    return json_response({"data": "hello world"})

@routes.post('/redis')
async def post_redis(request):
    data = await request.json()
    redis_key = data["key"]
    redis_val = data["value"]
    r = redis.Redis(decode_responses=True)
    r.set(redis_key, redis_val)
    return json_response({"data": f"key:{redis_key}, value:{redis_val} stored successfully"})

@routes.get('/redis')
async def get_redis(request):
    key: str = request.rel_url.query.get('key')
    if key is None:
        return json_response({"error": "Query Paramerer 'key' is needed"}, status=400)
    r = redis.Redis(decode_responses=True)
    val = r.get(key)
    if val is None:
        return json_response({"error": f"Data of {key} is not found"}, status=404)
    return json_response({"data":val}) 

# Infra Layer
def init_redis():
    redis.Redis(host="localhost", port=6379)

app = web.Application()
app.router.add_routes(routes=routes)


if __name__ == '__main__':
    init_redis()
    web.run_app(app)