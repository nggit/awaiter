# Copyright (c) 2024 nggit

__version__ = '0.0.4'
__all__ = ('ThreadExecutor',)

import asyncio  # noqa: E402

from functools import wraps  # noqa: E402
from inspect import isgenerator, isgeneratorfunction  # noqa: E402
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
        self._shutdown = None

    async def __aenter__(self):
        return self.start()

    async def __aexit__(self, exc_type, exc, tb):
        await self.shutdown()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.submit(func, *args, **kwargs)

        return wrapper

    def start(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        if self._shutdown is None:
            self._shutdown = self._loop.create_future()

        if not self._shutdown.done():
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
                if (isinstance(exc, StopIteration) and
                        isgenerator(getattr(func, '__self__'))):
                    # StopIteration interacts badly with generators
                    # and cannot be raised into a Future
                    self._loop.call_soon_threadsafe(fut.cancel)
                else:
                    self._loop.call_soon_threadsafe(set_exception, fut, exc)

        self._loop.call_soon_threadsafe(set_result, self._shutdown, None)

    def submit(self, func, *args, **kwargs):
        if not self.is_alive() or self._shutdown.done():
            raise RuntimeError(
                'calling submit() before start() or after shutdown()'
            )

        if isgeneratorfunction(func):
            gen = func(*args, **kwargs)

            @wraps(func)
            async def wrapper():
                while True:
                    fut = self._loop.create_future()
                    self.queue.put_nowait((fut, gen.__next__, (), {}))

                    try:
                        yield await fut
                    except asyncio.CancelledError:
                        break

            return wrapper()

        fut = self._loop.create_future()
        self.queue.put_nowait((fut, func, args, kwargs))

        return fut

    def shutdown(self):
        if self.is_alive():
            self.queue.put_nowait((None, None, None, None))
        else:
            set_result(self._shutdown, None)

        return self._shutdown
