# Copyright (c) 2024 nggit

__version__ = '0.1.2'
__all__ = ('ThreadExecutor', 'MultiThreadExecutor')

import asyncio  # noqa: E402

from functools import wraps  # noqa: E402
from inspect import isgeneratorfunction  # noqa: E402
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
        self._shutdown = None

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
        super().start()

        return self

    def run(self):
        while True:
            fut, func, args, kwargs = self.queue.get()

            if func is None:
                if isinstance(fut, asyncio.Future):
                    self.loop.call_soon_threadsafe(self.join)
                    self.loop.call_soon_threadsafe(set_result, fut, None)

                break

            try:
                result = func(*args, **kwargs)

                self.loop.call_soon_threadsafe(set_result, fut, result)
            except BaseException as exc:
                if (isinstance(exc, StopIteration) and
                        hasattr(getattr(func, '__self__'), '__iter__')):
                    # StopIteration interacts badly with generators
                    # and cannot be raised into a Future
                    self.loop.call_soon_threadsafe(fut.cancel)
                else:
                    self.loop.call_soon_threadsafe(set_exception, fut, exc)

    def submit(self, func, *args, **kwargs):
        if not self.is_alive():
            raise RuntimeError(
                'calling submit() before start() or after shutdown()'
            )

        if isgeneratorfunction(func) or hasattr(func, '__iter__'):
            func = getattr(func, '__iter__', func)
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

        if callable(func):
            fut = self.loop.create_future()
            self.queue.put_nowait((fut, func, args, kwargs))

            return fut

        raise TypeError(f'{str(func)} is not callable or iterable')

    def shutdown(self):
        if self._shutdown is None:
            self._shutdown = self.loop.create_future()

        if self.is_alive():
            self.queue.put_nowait((self._shutdown, None, None, None))
        else:
            set_result(self._shutdown, None)

        return self._shutdown


class MultiThreadExecutor(ThreadExecutor):
    def __init__(self, size=5, loop=None, name='MultiThreadExecutor'):
        super().__init__(loop=loop, name=name)

        self.size = size
        self._threads = {}
        self._shutdown = None

    def is_alive(self):
        for thread in self._threads.values():
            if thread.is_alive():
                return True

        return False

    def start(self):
        super().start()
        self._threads[self.name] = super()

        return self

    def run(self):
        try:
            super().run()
            self.size -= 1
        finally:
            self.loop.call_soon_threadsafe(current_thread().join)

            if current_thread().name in self._threads:
                del self._threads[current_thread().name]

        # exited normally. signal the next thread to stop as well
        self.loop.call_soon_threadsafe(self.shutdown)

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
        if self._shutdown is None:
            self._shutdown = self.loop.create_future()

        if self.is_alive():
            self.queue.put_nowait((None, None, None, None))
        else:
            set_result(self._shutdown, None)

        return self._shutdown
