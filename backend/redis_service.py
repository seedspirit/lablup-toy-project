import asyncio, pickle, json, logging

from redis import Redis
from redis.client import PubSub

from aiohttp.web import WebSocketResponse
from aiohttp import WSMsgType

PUBSUB_FIELD_TYPE = "type"
PUBSUB_FIELD_DATA = "data"
PUBSUB_TYPE_MESSAGE = "message"

class RedisService():

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def create_pubsub(self) -> PubSub:
        return self.redis_client.pubsub()
    
    def subscribe(self, channel_name: str, pubsub: PubSub) -> None:
        pubsub.subscribe(channel_name)

    def unsubscribe(self, channel_name: str, pubsub: PubSub) -> None:
        pubsub.unsubscribe(channel_name)

    def pubsub_close(self, pubsub: PubSub) -> None:
        pubsub.close()

    async def receive_chat_message(self, websocket: WebSocketResponse, pubsub: PubSub) -> None:
        while not websocket.closed:
            message = pubsub.get_message()
            if message and message[PUBSUB_FIELD_TYPE] == PUBSUB_TYPE_MESSAGE:
                try:
                    await websocket.send_json(pickle.loads(message[PUBSUB_FIELD_DATA]))
                except:
                    break
            await asyncio.sleep(0.01)
        
    async def publish_chat_message(self, websocket: WebSocketResponse, channel_name: str) -> None:
        while not websocket.closed:
            try:   
                msg = await websocket.receive() 

                if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING):
                    break

                data = json.loads(msg.data)
                chat = {
                    "from": data["user_id"],
                    "date": data["timestamp"],
                    "message": data["message"],
                }
                self.redis_client.publish(channel=channel_name, message=pickle.dumps(chat))

            except Exception as e:
                logging.error(f"Error in WebSocket loop: {e}", exc_info=True)
                break