import aiohttp_session
import container
from router import routes
from aiohttp import web
from container import Container

if __name__ == '__main__':
    container = Container()

    app = web.Application()
    app.add_routes(routes)
    app['container'] = container
    
    aiohttp_session.setup(app=app, storage=container.redis_storage)
    
    web.run_app(app, port=80)