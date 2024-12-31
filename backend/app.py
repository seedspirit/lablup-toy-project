from aiohttp import web

import aiohttp_session
from config import redis_storage
from router import routes

app = web.Application()
app.add_routes(routes)
aiohttp_session.setup(app=app, storage=redis_storage)

if __name__ == '__main__':
    web.run_app(app)