from aiohttp import web

routes = web.RouteTableDef()

@routes.get('/')
async def handler(request):
    return web.json_response({"data": "hello world"})

app = web.Application()
app.router.add_routes(routes=routes)


if __name__ == '__main__':
    web.run_app(app)