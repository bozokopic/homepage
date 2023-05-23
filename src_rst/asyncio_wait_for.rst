Beware of `asyncio.wait_for`
============================

Python `asyncio`_ library provides event loop implementation with
coroutine based interface. Usage of this library greatly improves development
process involved in structuring applications with concurrent task executions.
Nevertheless, this kind of problems require deep understanding of
underling concepts, even if they are wrapped in user-friendly interface.
Failure to understand implementation and interface limitations can lead to
hard to detect bugs.

This article observes behavior of `asyncio.wait_for`_ implementation
and identifies some of unexpected edge cases. Understanding of
basic `asyncio` concepts, such as coroutines, tasks and futures, is assumed
(see `Coroutines and Tasks`_).

.. note::

    This article references `asyncio.wait_for` implementation available
    in CPython 3.11.3. Similar behavior can be observed in prior versions.


Introduction
------------

`wait_for` is one of basic `asyncio` utility functions which enables
cancellation of task/future based on elapsed time. It accepts single
`awaitable`_ object and timeout. If provided awaitable object is coroutine,
new task is created and coroutine execution is scheduled.

By accepting any kind of coroutine, `wait_for` can be used as generic timeout
utility. Individual coroutine implementations do not have to provide timeout
arguments and implement additional timeout logic. Responsibility of timeout
functionality is delegated to code calling coroutine which should be canceled
based on timeout. Because of this inversion of responsibility, execution
timeout can be applied event to those coroutines which are not initially
written with timeout operation in mind.

To demonstrate basic usage of `wait_for`, we can utilize `asyncio.sleep`_:

.. code:: python

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

At first `wait_for` occurrence, `sleep` is called with delay argument shorter
than timeout argument. In case of second `wait_for` call, `sleep` is scheduled
with longer delay than timeout provided to `wait_for`. Taking into account
these relations between delay and timeout parameters, we can expect following
output::

    first finished
    second timeout

`Example 1 source code`_


`wait_for` stopping cancellation propagation
--------------------------------------------

`asyncio` provides mechanism for `task cancellation`_ based on exception
propagation. This generic mechanism enables cancellation of any kind of tasks
as long as all executing coroutines propagate `asyncio.CancelledError`_.
If any coroutine fails to propagate this exception, task cancellation will
fail and often result in unwanted behavior.

Because `wait_for` is basic function widely used by other coroutines, it
is reasonable to expect that it will always successfully propagate
`CancelledError` and therefor support correct cancellation. Nevertheless, this
is not always the case. Following examples explore conditions when
`wait_for` stops cancellation propagation.


Simple producer/consumer
''''''''''''''''''''''''

To help us in identifying this edge-cases, we will use simple producer/consumer
model where synchronization between producer and consumer is based on
`asyncio.Queue`_.

Producer is modeled with coroutine which adds new entries to queue at regular
intervals:

.. code:: python

    async def produce(queue: asyncio.Queue):
        try:
            for i in itertools.count(1):
                queue.put_nowait(i)
                await asyncio.sleep(1)

        finally:
            print('closing produce')

Consumer is modeled with coroutine which waits for new entries. Once entry
is available in queue, consumer will print entry to standard output and
continue waiting for new entries indefinitely:

.. code:: python

    async def consume(queue: asyncio.Queue):
        try:
            while True:
                result = await queue.get()
                print(result)

        finally:
            print('closing consume')

Additional "work" is represented with coroutine which sleeps based on
provided delay:

.. code:: python

    async def other_work(delay: float):
        await asyncio.sleep(delay)

Producer and consumer are run as new tasks which are cancelled after additional
work is done:

.. code:: python

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

By running this code, we can expect::

    1
    2
    3
    closing produce
    closing consume

`Example 2 source code`_


Consumer with `wait_for`
''''''''''''''''''''''''

To introduce `wait_for`, we can change `consume` from previous example with:

.. code:: python

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

New implementation of `consume` waits for queued entries with provided
timeout. If timeout occurs, ``timeout`` is printed to standard output and
loop starts from beginning.

Running this example will result in::

    1
    timeout
    2
    timeout
    3
    closing produce
    closing consume

`Example 3 source code`_


`wait_for` ignoring cancellation
''''''''''''''''''''''''''''''''

In previous example, if we change `other_work`'s delay to ``0``:

.. code:: python

    await other_work(0)

unexpected result occurs::

    closing produce
    1
    timeout
    timeout
    timeout
    timeout
    ...

Execution of this example newer finishes because consumer is not successfully
canceled. Because `wait_for` is only coroutine awaited in `consume`, we
can assume that `wait_for` did not propagate `CancelledError`.

`Example 4 source code`_


Focusing on consumer
''''''''''''''''''''

To focus only on consumer, we can skip producer's task creation:

.. code:: python

    queue = asyncio.Queue()

    consumer = asyncio.create_task(consume(queue))

    await other_work(0)

    consumer.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await consumer

Just by removing producer, consumer task is successfully canceled::

    closing consume

`Example 5 source code`_


Identifying edge-case
'''''''''''''''''''''

Because producer and consumer only interact through queue, we can expect that
queue state is significant in occurrence of unwanted behavior. To test this
hypothesis, instead of empty queue, non empty queue is provided to `consume`:

.. code:: python

    queue = asyncio.Queue()
    queue.put_nowait(1)

This change is sufficient for introduction of unwanted behavior::

    1
    timeout
    timeout
    timeout
    timeout
    ...

This example demonstrates that behavior of `wait_for` is dependent of
provided awaitable's behavior which can even result in stopping
`CancelledError` propagation. To accomplish this, we have used
``asyncio.sleep(0)`` as a way to schedule precise task cancellation depending
on task creation. Same sequence of `create_task` and `cancel` calls can easily
occur in real-word scenarios. Because of this, great care must be taken when
`wait_for` is used, taking into account behavior of provided awaitable and
possible cancellation timing of task executing `wait_for`.

`Example 6 source code`_


Alternative implementation
--------------------------

`hat-aio`_ implements `hat.aio.wait_for`_ which can be used as drop-in
replacement for `asyncio.wait_for`_. Together with propagation of
`CancelledError`, this implementation provides
`hat.aio.CancelledWithResultError`_. `CancelledWithResultError` extends
`CancelledError` with additional result/exception. This result/exception
contains awaitable's result in case when result is available and `wait_for`
is cancelled at the same time. Because this exception is also `CancelledError`,
all existing code catching `CancelledError` will continue to work.
In cases where obtaining result is necessary, even when `CancelledError` is
raised (e.g. result is associated with resource which requires explicit
cleanup), `CancelledWithResultError` can be used.


`asyncio.wait_for` example
''''''''''''''''''''''''''

In this example, awaitable produces result at the same time waiting task
is canceled:

.. code:: python

    async def do_work(future: asyncio.Future):
        await asyncio.sleep(1)
        return 42

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

Running this example results in::

    work task done False
    wait task done False
    42

`Example 7 source code`_


`hat.aio.wait_for` example
''''''''''''''''''''''''''

If we replace `asyncio.wait_for` with `hat.aio.wait_for`:

.. code:: python

    wait_task = asyncio.create_task(hat.aio.wait_for(work_task, timeout=2))

result is::

    work task done False
    wait task done False
    cancelled

If obtaining result is required, `CancelledError` can be replaced with
`CancelledWithResultError`:

.. code:: python

    except hat.aio.CancelledWithResultError as e:
        print('cancelled with result', e.result)

which results is::

    work task done False
    wait task done False
    cancelled with result 42

`Example 8 source code`_


.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _asyncio.wait_for: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
.. _Coroutines and Tasks: https://docs.python.org/3/library/asyncio-task.html
.. _awaitable: https://docs.python.org/3/library/asyncio-task.html#asyncio-awaitables
.. _asyncio.sleep: https://docs.python.org/3/library/asyncio-task.html#asyncio.sleep
.. _task cancellation: https://docs.python.org/3/library/asyncio-task.html#task-cancellation
.. _asyncio.CancelledError: https://docs.python.org/3/library/asyncio-exceptions.html#asyncio.CancelledError
.. _asyncio.Queue: https://docs.python.org/3/library/asyncio-queue.html#asyncio.Queue
.. _hat-aio: https://hat-aio.hat-open.com/
.. _hat.aio.wait_for: https://hat-aio.hat-open.com/py_api/hat/aio.html#wait_for
.. _hat.aio.CancelledWithResultError: https://hat-aio.hat-open.com/py_api/hat/aio.html#CancelledWithResultError

.. _Example 1 source code: asyncio_wait_for/example1.py
.. _Example 2 source code: asyncio_wait_for/example2.py
.. _Example 3 source code: asyncio_wait_for/example3.py
.. _Example 4 source code: asyncio_wait_for/example4.py
.. _Example 5 source code: asyncio_wait_for/example5.py
.. _Example 6 source code: asyncio_wait_for/example6.py
.. _Example 7 source code: asyncio_wait_for/example7.py
.. _Example 8 source code: asyncio_wait_for/example8.py
