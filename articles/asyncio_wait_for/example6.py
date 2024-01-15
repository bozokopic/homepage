import asyncio


async def do_work(future: asyncio.Future):
    await asyncio.sleep(1)
    return 42


async def main():
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    work_task = asyncio.create_task(do_work(future))
    wait_task = asyncio.create_task(asyncio.wait_for(work_task, timeout=2))

    await asyncio.sleep(1)

    print('work task done', work_task.done())
    print('wait task done', wait_task.done())
    wait_task.cancel()

    try:
        result = await wait_task
        print(result)

    except asyncio.CancelledError:
        print('cancelled')


if __name__ == '__main__':
    asyncio.run(main())
