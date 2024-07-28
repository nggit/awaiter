# awaiter

[![codecov](https://codecov.io/gh/nggit/awaiter/branch/main/graph/badge.svg?token=E6GK8YQ26P)](https://codecov.io/gh/nggit/awaiter)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=nggit_awaiter&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=nggit_awaiter)

Makes your blocking functions *awaitable*.

`awaiter.ThreadExecutor()` represents a single thread that you can use to execute blocking functions in a FIFO manner.
It does not use a thread pool like [asyncio.to_thread()](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread) or [loop.run_in_executor()](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor), to keep it minimal and predictable.

## Usage
```python
import asyncio
import time

from awaiter import ThreadExecutor


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

from awaiter import ThreadExecutor

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
    # the thread will be closed.
    # if you want to wait until all queued tasks are completed:
    # await executor.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
```

If you want to execute multiple tasks at once without waiting in the main thread, use `executor.submit()`:
```python
# ...

    fut1 = executor.submit(blocking_function, 'World')
    fut2 = executor.submit(blocking_function, 'Foo')
    fut3 = executor.submit(blocking_function, 'Bar')

# ...
```

Last but not least, it also supports generator functions:
```python
# ...

@executor
def generator_function(name):
    yield 'Hello, '
    time.sleep(1)
    yield name
    yield '!'

# ...

    async for data in generator_function('World'):
        print(data)

# ...
```
## But I want a thread pool?
We provide the `awaiter.MultiThreadExecutor` helper.

It has a thread pool-like approach and is more suitable for use as a single, persistent object:

```python
executor = MultiThreadExecutor(size=10)
```

How to use is the same, as the interface is identical to `awaiter.ThreadExecutor`.

## Install
```
python3 -m pip install --upgrade awaiter
```

## License
MIT
