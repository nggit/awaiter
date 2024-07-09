# Copyright (c) 2024 nggit

__version__ = '0.0.0'
__all__ = ('ThreadExecutor',)

import asyncio  # noqa: E402
import queue  # noqa: E402
import threading  # noqa: E402

from functools import wraps  # noqa: E402


class ThreadExecutor(threading.Thread):
    def __init__(self, loop=None, **kwargs):
        super().__init__(**kwargs)

        self.queue = queue.SimpleQueue()
        self._loop = loop

    async def __aenter__(self):
        return self.start()

    async def __aexit__(self, exc_type, exc, tb):
        self.shutdown()

    def __call__(self, func):
        return self.coroutine(func)

    def coroutine(self, func):
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

                self._loop.call_soon_threadsafe(fut.set_result, result)
            except BaseException as exc:
                self._loop.call_soon_threadsafe(fut.set_exception, exc)

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
