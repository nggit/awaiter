# Copyright (c) 2024 nggit

import asyncio
import sys
import time
import unittest

from asyncutor import ThreadExecutor, MultiThreadExecutor


class TestThreadExecutor(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.executor = ThreadExecutor(loop=self.loop)
        self.executor.start()

    def tearDown(self):
        self.loop.run_until_complete(self.executor.shutdown())
        self.loop.close()

        self.assertEqual(self.executor.queue.qsize(), 0)

    def test_result(self):
        def blocking_function(name):
            return f'Hello, {name}!'

        async def test():
            result = await self.executor(blocking_function)('World')
            self.assertEqual(result, 'Hello, World!')

        self.loop.run_until_complete(test())

    def test_exception(self):
        @self.executor
        def blocking_function():
            sys.exit(1)

        async def test():
            with self.assertRaises(SystemExit) as cm:
                await blocking_function()

            self.assertEqual(str(cm.exception), '1')

        self.loop.run_until_complete(test())

    def test_multiple_tasks(self):
        def blocking_function(name):
            time.sleep(0.25)
            return f'Hello, {name}!'

        async def test():
            # submit to the thread without waiting
            fut1 = self.executor.submit(blocking_function, 'Foo')
            fut2 = self.executor.submit(blocking_function, 'Bar')

            await asyncio.sleep(1)
            # after 1 seconds there should be a result without these:
            # await fut1
            # await fut2

            self.assertEqual(fut1.result(), 'Hello, Foo!')
            self.assertEqual(fut2.result(), 'Hello, Bar!')

        self.loop.run_until_complete(test())

    def test_context_manager(self):
        executor = ThreadExecutor()

        @executor
        def blocking_function(name):
            return f'Hello, {name}!'

        async def test():
            async with executor:
                result = await blocking_function('World')
                self.assertEqual(result, 'Hello, World!')

        self.loop.run_until_complete(test())

    def test_generator_function(self):
        @self.executor
        def generator_function(name):
            yield b'Hello, '
            time.sleep(0.1)
            yield name
            yield b'!'

        async def test():
            result = bytearray()

            async for data in generator_function(b'World'):
                result.extend(data)

            self.assertEqual(result, b'Hello, World!')

        self.loop.run_until_complete(test())

    def test_cancel_future(self):
        def blocking_function():
            return

        async def test():
            fut = self.executor.submit(blocking_function)
            fut.cancel()

            await asyncio.sleep(1)
            self.assertTrue(fut.done())

        self.loop.run_until_complete(test())

    def test_submit_before_start(self):
        executor = MultiThreadExecutor(1)

        with self.assertRaises(RuntimeError) as cm:
            executor.submit(None)

        self.assertEqual(
            str(cm.exception),
            'calling submit() before start() or after shutdown()'
        )

    def test_submit_after_shutdown(self):
        self.loop.run_until_complete(self.executor.shutdown())

        with self.assertRaises(RuntimeError) as cm:
            self.executor.submit(None)

        self.assertEqual(
            str(cm.exception),
            'calling submit() before start() or after shutdown()'
        )

    def test_shutdown(self):
        fut = self.executor.shutdown()
        self.loop.run_until_complete(fut)

        self.assertTrue(fut.done())
        self.assertFalse(self.executor.is_alive())

    def test_multithread_executor(self):
        def blocking_function(name):
            time.sleep(0.1)
            return f'Hello, {name}!'

        async def test():
            for size in (1, 2, 10):
                async with MultiThreadExecutor(size) as executor:
                    fut1 = executor(blocking_function)('Foo')
                    fut2 = executor(blocking_function)('Bar')

                    # test early shutdown
                    await executor.shutdown()
                    # await fut1
                    # await fut2

                    self.assertEqual(executor.queue.qsize(), 0)
                    self.assertEqual(fut1.result(), 'Hello, Foo!')
                    self.assertEqual(fut2.result(), 'Hello, Bar!')

                self.assertEqual(executor.queue.qsize(), 0)

        self.loop.run_until_complete(test())


if __name__ == '__main__':
    unittest.main()
