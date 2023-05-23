import asyncio


async def main():
    try:
        await asyncio.wait_for(asyncio.sleep(0.5), timeout=1)
        print('first finished')

    except TimeoutError:
        print('first timeout')

    try:
        await asyncio.wait_for(asyncio.sleep(1), timeout=0.5)
        print('second finished')

    except TimeoutError:
        print('second timeout')


if __name__ == '__main__':
    asyncio.run(main())
