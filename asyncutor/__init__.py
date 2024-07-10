# Copyright (c) 2024 nggit

__version__ = '0.0.1'
__all__ = ('ThreadExecutor',)

import asyncio  # noqa: E402

from functools import wraps  # noqa: E402
from queue import SimpleQueue  # noqa: E402
from threading import Thread  # noqa: E402


def set_result(fut, result):
    if not fut.done():
        fut.set_result(result)


def set_exception(fut, exc):
    if not fut.done():
        fut.set_exception(exc)


class ThreadExecutor(Thread):
    def __init__(self, loop=None, **kwargs):
        super().__init__(**kwargs)

        self.queue = SimpleQueue()
        self._loop = loop

    async def __aenter__(self):
        return self.start()

    async def __aexit__(self, exc_type, exc, tb):
        self.shutdown()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.submit(func, *args, **kwargs)

        return wrapper

    def start(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        super().start()
        return self

    def run(self):
        while True:
            fut, func, args, kwargs = self.queue.get()

            if func is None:
                break

            try:
                result = func(*args, **kwargs)

                self._loop.call_soon_threadsafe(set_result, fut, result)
            except BaseException as exc:
                self._loop.call_soon_threadsafe(set_exception, fut, exc)

    def submit(self, func, *args, **kwargs):
        if self._loop is None:
            raise RuntimeError('calling submit() before start()')

        fut = self._loop.create_future()
        self.queue.put_nowait((fut, func, args, kwargs))

        return fut

    def shutdown(self, wait=True):
        if self._loop is None:
            raise RuntimeError('calling shutdown() before start()')

        self.queue.put_nowait((None, None, None, None))

        if wait:
            self.join()
