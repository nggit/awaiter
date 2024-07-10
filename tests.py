# Copyright (c) 2024 nggit

import asyncio
import sys
import time
import unittest

from asyncutor import ThreadExecutor


class TestThreadExecutor(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.executor = ThreadExecutor(loop=self.loop)
        self.executor.start()

    def tearDown(self):
        self.executor.shutdown()
        self.loop.close()

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
            time.sleep(1)
            return f'Hello, {name}!'

        async def test():
            # submit to the thread without waiting
            fut1 = self.executor.submit(blocking_function, 'Foo')
            fut2 = self.executor.submit(blocking_function, 'Bar')

            await asyncio.sleep(3)
            # after 3 seconds there should be a result without these:
            # await fut1
            # await fut2

            self.assertEqual(fut1.result(), 'Hello, Foo!')
            self.assertEqual(fut2.result(), 'Hello, Bar!')

        self.loop.run_until_complete(test())

    def test_context_manager(self):
        executor = ThreadExecutor()

        @executor
        def blocking_function():
            return None

        async def test():
            async with executor:
                result = await blocking_function()
                self.assertEqual(result, None)

        self.loop.run_until_complete(test())

    def test_submit_before_start(self):
        executor = ThreadExecutor()

        with self.assertRaises(RuntimeError) as cm:
            executor.submit(None)

        self.assertEqual(str(cm.exception), 'calling submit() before start()')

    def test_shutdown_before_start(self):
        executor = ThreadExecutor()

        with self.assertRaises(RuntimeError) as cm:
            executor.shutdown()

        self.assertEqual(
            str(cm.exception), 'calling shutdown() before start()'
        )

    def test_shutdown(self):
        self.executor.shutdown()
        self.assertFalse(self.executor.is_alive())


if __name__ == '__main__':
    unittest.main()
