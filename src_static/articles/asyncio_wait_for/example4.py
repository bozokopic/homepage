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
            try:
                result = await asyncio.wait_for(queue.get(), timeout=0.5)
                print(result)

            except asyncio.TimeoutError:
                print('timeout')

    finally:
        print('closing consume')


async def other_work(delay: float):
    await asyncio.sleep(delay)


async def main():
    queue = asyncio.Queue()

    producer = asyncio.create_task(produce(queue))
    consumer = asyncio.create_task(consume(queue))

    await other_work(0)

    producer.cancel()
    consumer.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await producer

    with contextlib.suppress(asyncio.CancelledError):
        await consumer


if __name__ == '__main__':
    asyncio.run(main())
