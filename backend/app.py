from aiohttp import web

import aiohttp_session
from container import container
from router import routes


if __name__ == '__main__':    
    app = web.Application()
    app.add_routes(routes)
    
    aiohttp_session.setup(app=app, storage=container.redis_storage)
    
    web.run_app(app)