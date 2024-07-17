# Copyright (c) 2024 nggit

__version__ = '0.0.6'
__all__ = ('ThreadExecutor', 'MultiThreadExecutor')

import asyncio  # noqa: E402

from functools import wraps  # noqa: E402
from inspect import isgenerator, isgeneratorfunction  # noqa: E402
from queue import SimpleQueue  # noqa: E402
from threading import Thread, current_thread  # noqa: E402


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
        self._shutdown_waiter = None

    @property
    def loop(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        return self._loop

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
        if self._shutdown_waiter is None:
            self._shutdown_waiter = self.loop.create_future()

        if not self._shutdown_waiter.done():
            super().start()

        return self

    def run(self):
        while True:
            fut, func, args, kwargs = self.queue.get()

            if func is None:
                break

            try:
                result = func(*args, **kwargs)

                self.loop.call_soon_threadsafe(set_result, fut, result)
            except BaseException as exc:
                if (isinstance(exc, StopIteration) and
                        isgenerator(getattr(func, '__self__'))):
                    # StopIteration interacts badly with generators
                    # and cannot be raised into a Future
                    self.loop.call_soon_threadsafe(fut.cancel)
                else:
                    self.loop.call_soon_threadsafe(set_exception, fut, exc)

        self.loop.call_soon_threadsafe(set_result, self._shutdown_waiter, None)

    def submit(self, func, *args, **kwargs):
        if not self.is_alive():
            raise RuntimeError(
                'calling submit() before start() or after shutdown()'
            )

        if isgeneratorfunction(func):
            gen = func(*args, **kwargs)

            @wraps(func)
            async def wrapper():
                while True:
                    fut = self.loop.create_future()
                    self.queue.put_nowait((fut, gen.__next__, (), {}))

                    try:
                        yield await fut
                    except asyncio.CancelledError:
                        break

            return wrapper()

        fut = self.loop.create_future()
        self.queue.put_nowait((fut, func, args, kwargs))

        return fut

    def shutdown(self):
        if self.is_alive():
            self.queue.put_nowait((None, None, None, None))
        else:
            set_result(self._shutdown_waiter, None)

        return self._shutdown_waiter


class MultiThreadExecutor(ThreadExecutor):
    def __init__(self, size=10, loop=None):
        super().__init__(loop=loop, name='MultiThreadExecutor')

        self.size = size
        self._threads = {}
        self._shutdown = None

    def is_alive(self):
        return bool(self._threads)

    def start(self):
        if self._shutdown is None:
            self._shutdown = self.loop.create_future()

        if not self._shutdown.done():
            super().start()
            self._threads[self.name] = super()

        return self

    def run(self):
        try:
            super().run()
            self.size -= 1
        finally:
            if current_thread().name in self._threads:
                del self._threads[current_thread().name]

        for thread in self._threads.values():
            if thread.is_alive():
                # exited normally. signal the next thread to stop as well
                self.queue.put_nowait((None, None, None, None))
                break
        else:
            self.loop.call_soon_threadsafe(set_result, self._shutdown, None)

    def submit(self, *args, **kwargs):
        fut = super().submit(*args, **kwargs)
        num = len(self._threads)

        if num < self.size:
            thread = Thread(
                target=self.run, name=f'{self.name}.{num}.{self.loop.time()}'
            )
            thread.start()
            self._threads[thread.name] = thread

        return fut

    def shutdown(self):
        if not self.is_alive():
            set_result(self._shutdown, None)

        return asyncio.wait([super().shutdown(), self._shutdown])
