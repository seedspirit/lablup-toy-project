import asyncio
import aiohttp_session
import weakref, logging

from signal import SIGTERM, SIGINT
from router import routes
from aiohttp import WSCloseCode, web
from container import Container

class ServerApplication:
    def __init__(self, container: Container):
        self.app = None
        self.container = container
    
    async def create(self) -> web.Application:
        self.app = web.Application()
        
        self.app.add_routes(routes)
        self.app.on_shutdown.append(self._on_shutdown)
        
        self.app['container'] = self.container
        self.app['active_websockets'] = weakref.WeakSet()
        
        aiohttp_session.setup(app=self.app, storage=self.container.redis_storage)
        
        await self._register_signal_handler()
        
        return self.app

    async def _on_shutdown(self, app: web.Application) -> None:
        logging.info("Server shutdown...")
        
        # 남아있는 websocket 연결 종료
        logging.info("Closing active websockets...")
        ws_close_tasks = [
            ws.close(code=WSCloseCode.GOING_AWAY, message='Server shutdown') 
            for ws in app['active_websockets']
        ]
        await asyncio.gather(*ws_close_tasks)
        
        # Redis 연결 종료
        logging.info("Closing Redis connection...")
        self.container.redis_client.close()

        # 남은 태스크 종료
        tasks = asyncio.all_tasks() - {asyncio.current_task()}
        if not tasks:
            return
        
        logging.info("Cancelling remain tasks...")
        for task in tasks:
            task.cancel()
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logging.error("Failed to cancel tasks: %s", e, exc_info=True)

    async def _register_signal_handler(self) -> None:
        loop = asyncio.get_event_loop()
        for signal in (SIGTERM, SIGINT):
            loop.add_signal_handler(
                sig=signal, 
                callback=lambda: asyncio.create_task(self.app.cleanup())
            )