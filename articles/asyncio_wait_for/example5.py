import asyncio
import contextlib


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
    queue.put_nowait(1)

    consumer = asyncio.create_task(consume(queue))

    await other_work(0)

    consumer.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await consumer


if __name__ == '__main__':
    asyncio.run(main())
