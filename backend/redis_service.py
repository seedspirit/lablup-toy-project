import asyncio, pickle, json, logging
from typing import Any

from redis import Redis
from redis.client import PubSub

from aiohttp.web import WebSocketResponse
from aiohttp import WSMsgType

from exceptions import MessagePublishException, MessageReceiveException, WebSocketException

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
                except Exception as e:
                    logging.error(f"Error sending message to WebSocket: {e}", exc_info=True)
                    raise MessageReceiveException("Error receiving messages from the server.")
            await asyncio.sleep(0.01)
        
    async def publish_chat_message(self, websocket: WebSocketResponse, channel_name: str) -> None:
        while not websocket.closed:
            message: dict[str, Any] | None = await self._recevie_websocket_message(websocket=websocket)
            if not message: 
                return

            await self._publish_message_to_redis(channel_name=channel_name, message=message)
    
    async def _recevie_websocket_message(self, websocket: WebSocketResponse) -> dict | None:
        try:   
            msg = await websocket.receive() 

            if msg.type == WSMsgType.ERROR:
                raise WebSocketException("WebSocket error occurred")
        
            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING):
                return

            data = json.loads(msg.data)
            chat = {
                "from": data["user_id"],
                "date": data["timestamp"],
                "message": data["message"],
            }

            return chat
            
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON format: {e}", exc_info=True)
            raise WebSocketException("Invalid message format")

        except Exception as e:
            logging.error(f"Error receiving WebSocket message: {e}", exc_info=True)
            raise WebSocketException("WebSocket connection encountered an error")

    async def _publish_message_to_redis(self, channel_name: str, message: dict) -> None:
        try:
            self.redis_client.publish(channel=channel_name, message=pickle.dumps(message))
        except Exception:
            raise MessagePublishException("Error publishing your message to the server.")