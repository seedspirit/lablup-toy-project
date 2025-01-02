import asyncio
import aiohttp_session
import weakref, logging

from signal import SIGTERM, SIGINT
from router import routes
from aiohttp import WSCloseCode, web
from container import Container

async def create_app() -> web.Application:
    container = Container()

    app = web.Application()
    app.add_routes(routes)
    app.on_shutdown.append(on_shutdown)

    app['container'] = container
    app['active_websockets'] = weakref.WeakSet()
    
    aiohttp_session.setup(app=app, storage=container.redis_storage)

    await register_signal_handler(app)
    
    return app

async def on_shutdown(app: web.Application) -> None:
    logging.info("Server shutdown...")

    # 남아있는 websocker 연결 종료
    logging.info("Closing active websockets...")
    ws_close_tasks = [
        ws.close(code=WSCloseCode.GOING_AWAY, message='Server shutdown') for ws in app['active_websockets']
    ]
    await asyncio.gather(*ws_close_tasks)
    
    # Redis 연결 종료
    logging.info("Closing Redis connection...")
    container: Container = app['container']
    container.redis_client.close()

async def register_signal_handler(app: web.Application) -> None:
    loop = asyncio.get_event_loop()
    for signal in (SIGTERM, SIGINT):
        loop.add_signal_handler(sig=signal, callback=lambda: asyncio.create_task(app.cleanup()))