import asyncio
import contextlib
import itertools


async def produce(queue: asyncio.Queue):
    try:
        for i in itertools.count(1):
            queue.put_nowait(i)
            await asyncio.sleep(1)

    finally:
        print('closing produce')


async def consume(queue: asyncio.Queue):
    try:
        while True:
            result = await queue.get()
            print(result)

    finally:
        print('closing consume')


async def other_work(delay: float):
    await asyncio.sleep(delay)


async def main():
    queue = asyncio.Queue()

    producer = asyncio.create_task(produce(queue))
    consumer = asyncio.create_task(consume(queue))

    await other_work(2.5)

    producer.cancel()
    consumer.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await producer

    with contextlib.suppress(asyncio.CancelledError):
        await consumer


if __name__ == '__main__':
    asyncio.run(main())
