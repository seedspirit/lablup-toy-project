import aiohttp_session
import argparse, multiprocessing

from router import routes
from aiohttp import web
from container import Container

def create_app() -> web.Application:
    container = Container()

    app = web.Application()
    app.add_routes(routes)
    app['container'] = container
    
    aiohttp_session.setup(app=app, storage=container.redis_storage)
    
    return app

def run_single_app() -> None:
    app = create_app()
    web.run_app(app, port=80, reuse_port=True)

def run_multi_process(process_count: int = 2) -> None:
    processes: list[multiprocessing.Process] = []
    for _ in range(process_count):
        process = multiprocessing.Process(target=run_single_app)
        process.start()
        processes.append(process)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    SINGLE_THREAD_MODE = 'thread'
    MULTI_PROCESS_MODE = 'multi-process'

    parser.add_argument('-m', '--mode', choices=[SINGLE_THREAD_MODE, MULTI_PROCESS_MODE], default=None)
    parser.add_argument('-w', '--workers', type=int, default=None)
    args = parser.parse_args()

    if args.mode is None:
        if args.workers:
            raise ValueError("Workers only available in multi-process mode")
        run_single_app()

    elif args.mode == SINGLE_THREAD_MODE:
        if args.workers:
            raise ValueError("Single-thread mode does not support workers")
        run_single_app()
    
    elif args.mode == MULTI_PROCESS_MODE:
        if args.workers is None:
            args.workers = 2
        if args.workers > multiprocessing.cpu_count():
            raise ValueError(f"Maximum workers is {multiprocessing.cpu_count()}")
        run_multi_process(process_count=args.workers)