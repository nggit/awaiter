# asyncutor
Makes your blocking functions *awaitable*.

`asyncutor.ThreadExecutor()` represents a single thread that you can use to execute blocking functions in a FIFO manner.
It does not use a thread pool like [asyncio.to_thread()](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread) or [loop.run_in_executor()](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor), to keep it minimal and predictable.

## Usage
```python
import asyncio
import time

from asyncutor import ThreadExecutor


def blocking_function(name):
    time.sleep(1)
    return f'Hello, {name}!'

async def main():
    async with ThreadExecutor() as executor:
        result = await executor(blocking_function)('World')
        print(result)

    # out of context, the thread is closed here

if __name__ == '__main__':
    asyncio.run(main())
```

Or use the decorator style:

```python
import asyncio
import time

from asyncutor import ThreadExecutor

executor = ThreadExecutor()


@executor
def blocking_function(name):
    time.sleep(1)
    return f'Hello, {name}!'

async def main():
    executor.start()

    result = await blocking_function('World')
    print(result)

    executor.shutdown()
    # the thread is closed here

if __name__ == '__main__':
    asyncio.run(main())
```

If you want to execute multiple tasks at once without waiting in the main thread, use `executor.submit()`:
```python
    fut1 = executor.submit(blocking_function, 'World')
    fut2 = executor.submit(blocking_function, 'Foo')
    fut3 = executor.submit(blocking_function, 'Bar')
```

## Install
```
python3 -m pip install --upgrade asyncutor
```

## License
MIT
