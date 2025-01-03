import asyncio, pickle, json, logging
from typing import Any

from redis import Redis
from redis.client import PubSub

from aiohttp.web import WebSocketResponse
from aiohttp import WSMsgType

from exceptions import *

PUBSUB_FIELD_TYPE = "type"
PUBSUB_FIELD_DATA = "data"
PUBSUB_TYPE_MESSAGE = "message"

class RedisService():

    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def _create_subscribed_pubsub(self, channel_name: str) -> PubSub:
        pubsub: PubSub = self.redis_client.pubsub()
        pubsub.subscribe(channel_name)
        return pubsub

    def _clean_up_pubsub(self, pubsub: PubSub, channel_name: str) -> None:
        pubsub.unsubscribe(channel_name)
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
            raise InvalidMessageFormatException("Invalid message format")

        except Exception as e:
            logging.error(f"Error receiving WebSocket message: {e}", exc_info=True)
            raise WebSocketException("WebSocket connection encountered an error")

    async def _publish_message_to_redis(self, channel_name: str, message: dict) -> None:
        try:
            self.redis_client.publish(channel=channel_name, message=pickle.dumps(message))
        except Exception:
            raise MessagePublishException("Error publishing your message to the server.")

    async def handle_chat_communication(self, websocket: WebSocketResponse, channel_name: str) -> None:
        pubsub = self._create_subscribed_pubsub(channel_name=channel_name)

        try:
            receive_task = asyncio.create_task(self.receive_chat_message(websocket=websocket, pubsub=pubsub))
            publish_task = asyncio.create_task(self.publish_chat_message(websocket=websocket, channel_name=channel_name))

            # 두 태스크 모두 ws이 close되거나 에러가 발생할 때까지 무한 루프로 실행된다
            done, pending = await asyncio.wait(
                [receive_task, publish_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 둘 중 하나가 에러 혹은 ws close로 완료되면 나머지 태스크도 정리
            for task in pending:
                # 태스크 취소 요청 후 기다린다            
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logging.error(f"Error during task cleanup: {task}", exc_info=True)
                    raise
        
        except (ChatServiceException, WebSocketException) as e:
            await websocket.send_json({"error": str(e)})

        except Exception as e:
            await websocket.send_json({"error": "An unexpected server error occurred."})

        finally:
            self._clean_up_pubsub(pubsub=pubsub, channel_name=channel_name)