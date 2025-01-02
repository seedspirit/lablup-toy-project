import argparse
import logging
import multiprocessing
import asyncio
import signal
import sys, os

from aiohttp import web
from app import create_app

def run_single_app() -> None:
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(create_app())
    web.run_app(app, port=80, reuse_port=True)

def handle_multiprocess_shutdown(processes, signum, frame) -> None:
    logging.info("Shutting down processes...")
    for process in processes:
        if process.is_alive():
            process.terminate()

    for process in processes:
        process.join()
    
    logging.info("All processes terminated.")
    sys.exit(0)

def run_multiprocess(process_count=2) -> None:
    processes: list[multiprocessing.Process] = []

    signal.signal(
        signal.SIGINT, 
        lambda signum, frame: handle_multiprocess_shutdown(processes=processes, signum=signum, frame=frame)
    )
    signal.signal(
        signal.SIGTERM, 
        lambda signum, frame: handle_multiprocess_shutdown(processes=processes, signum=signum, frame=frame)
    )

    for _ in range(process_count):
        process = multiprocessing.Process(target=run_single_app)
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

if __name__ == '__main__':
    logging.basicConfig(
        format = '%(asctime)s:%(levelname)s:%(message)s',
        datefmt = '%m/%d/%Y %I:%M:%S %p',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser()
    SINGLE_THREAD_MODE = 'thread'
    MULTI_PROCESS_MODE = 'multi-process'

    default_mode = os.getenv("APP_MODE", SINGLE_THREAD_MODE)
    default_workers = os.getenv("APP_WORKERS", 1)
    if default_workers:
        default_workers = int(default_workers)

    parser.add_argument('-m', '--mode', choices=[SINGLE_THREAD_MODE, MULTI_PROCESS_MODE], default=SINGLE_THREAD_MODE)
    parser.add_argument('-w', '--workers', type=int, default=None)
    args = parser.parse_args()

    if args.mode == SINGLE_THREAD_MODE:
        if args.workers > 1:
            raise ValueError("Cannot set workers more than 1 in single thread mode")
        run_single_app()

    elif args.mode == MULTI_PROCESS_MODE:
        if args.workers <= 1:
            raise ValueError("Workers must be at least 2 in multi-process mode")
        if args.workers > multiprocessing.cpu_count():
            raise ValueError(f"Maximum workers is {multiprocessing.cpu_count()}")
        run_multiprocess(process_count=args.workers)