`asyncio` resource management
=============================

This article analyzes resource management in applications based on Python's
`asyncio`_ library. As introduction, generic concept and significance of
resource management is explained. Concepts discussed in this section
are applicable to wide variety of implementations and are not specific to
`asyncio` or Python. Later, focus is shifted towards Python implementation and
`asyncio` library by explaining potential problems in usage of this library.
As a solution to noted problems, second part of this article presents
`hat-aio`_ utility library.

.. note::

    This article assumes familiarity with `asyncio`_ library and concepts
    such as `task cancellation`_ and distinction between
    `asyncio.Future`_, `asyncio.Task`_, coroutine function and coroutine object.


Procedural based architecture
-----------------------------

In procedural programming languages, functions are used as primary way to
organize code. Function implementation itself is defined as composition of other
function calls. This enables creation of higher levels of abstraction based on
previously defined functions and serves as efficient model for solving even the
most complex tasks. To enable this kind of composition, crucial part of
each function is its interface.

Function interface is usually defined by its arguments and return value. By
explicitly stating on which arguments function operates and what result function
produces, function provides basic method of encapsulation. Thus, function
implementation itself is regarded as "implementation detail" -
something that should not be primary concern for user of function. As long
as interface is obeyed, user can utilize function in any way necessary and
expect correct results.

In practice, function interface alone is not sufficient to recognize all
possible side effects of function execution. Together with shared state and
thread-local storage, even function arguments can hide not so obvious
encapsulation braking properties. In contrast to self-contained "plain data",
arguments can represent identifiers/references to stateful resources (e.g.
allocated memory, open file handles, sockets, ...). By accepting/returning
resource as part of its interface, function becomes part of resource management.
This imposes additional rules that are, in most languages, available only as
part of additional API documentation. Thus responsibility is shifted towards
function user which has to take into account resource lifetime and ownership
rules. Any kind of resource, that crosses single function boundary, has
potential to cause "resource leakage".

When function accepts resource as argument or returns resource as result,
care should be taken to inform function user of all side effects that function
has on resource state. In cases when function utilizes resource as
part of its implementation, without exposing it in function interface, it is
responsibility of function itself to properly create/manipulate/free resource
thus preventing "resource leaks".

All these constraints, that apply to classical procedural architectures,
also apply to other architectures that are built upon procedural
code organization. One example of these derived architectures is coroutine
based architecture.


Coroutine based architecture
----------------------------

Coroutines in modern programming languages (e.g. Python) are used as tool for
modeling concurrent algorithms. Ease of usage and their usability comes from
close mimicking of regular functions. Even though execution of statements inside
coroutine can be suspended/resumed, sequential execution and interface
definition is closely based on regular function model. Thus, most programmers
(that are usually well acquainted with procedural programming style) expect
similar behavior, in regard of resource management, as they expect from
regular functions.

Similarities between coroutines and functions can sometimes be deceptive.
By introduction of additional control flow rules, care must be taken to
expect different execution side-effects than in syntactically similar regular
functions. In case of Python, each `await` is potential place of suspending
execution, resuming execution, cancelling of current task or even permanent
stopping of task execution. Therefore, resource management must take into
account not strictly linear execution of coroutine statements.

To prevent "resource leaks", each "await" expression should expect possible
task cancellation and safely end resource usage. Python implements task
cancellation utilizing exception raising (`CancelledError`). Because of this,
`try/except/finally` blocks are often necessary part of resource
management which itself introduces additional nonlinear execution.

In Python `asyncio` library, concurrent execution threads, responsible for
execution of coroutine implementations, are represented with `tasks`. These
`tasks` are also resources and should be managed as any other resources.
Similarly to OS threads which should be "joined", execution lifetime of
`tasks` (including starting and stopping) should be monitored. Therefor,
each coroutine, spawning new task that are encapsulated as internal resources
(ones not crossing coroutine execution boundaries), should include cleanup
sequence ensuring that all newly spawned internal tasks have completed their
execution. For all tasks that are directly or indirectly part of coroutine
interface (input arguments or return values), ownership rules should be
clearly documented.


Uninterrupted task execution
----------------------------

Because coroutines introduce additional execution exit points, it can be
challenging to implement functionality that requires uninterrupted execution.
One of examples, where uninterrupted execution is required, is
resource cleanup procedures. When resource requires additional IO operations
and/or include execution time delays, resource cleanup procedures
are implemented as coroutines. To guarantee correct resource release, this
cleanup coroutine should usually have uninterrupted execution.

To analyze possible problems of resource usage and uninterrupted execution,
we can start with generic resource example:

.. code:: python

    async def do_work():
        resource = await create_resource()
        try:
            ...  # utilize resource to do some work
        finally:
            await cleanup_resource(resource)

    async def create_resource():
        ...  # create and return resource

    async def cleanup_resource():
        ...  # cleanup resource

In this simple example, resource usage is encapsulated as part of `do_work`
coroutine. Because resource is not part of `do_work`'s interface (directly or
indirectly), it is expected that `do_work` will correctly release resource
before its execution is done. This is the reason why `cleanup_resource` is
called as part of `finally` block.

If coroutine's `create_resource` and `cleanup_resource` are correctly
implemented (in regard of encapsulation/cleanup expectations), and if task
associated with `do_work` execution is not cancelled, this example correctly
models generic resource usage. But, if task executing `do_work` is cancelled,
this example can result in "resource leaks".

For example, we can expect cases where `do_work` is constrained with execution
time. If this execution time is exceeded, `do_work` should be canceled:

.. code:: python

    do_work_task = asyncio.create_task(do_work())
    await asyncio.wait_for(do_work_task, timeout)

With introduction of task cancellation, it is not clear if `do_work` will
correctly cleanup resource. Because task cancellation is mapped to raising
of `CancelledError`, if task is cancelled during execution of `try` block,
`finally` block will be executed thus releasing resource. But, if
`CancelledError` is raised during execution of `finally` block (e.g. `try`
block execution is finished), cleanup procedure could be interrupted while
resource is still not released. Because `asyncio` enables multiple cancellations
of same task, `CancelledError` can even be expected while `finally` block
is running as consequence of previous `CancelledError`.

To shield task from cancellation, `asyncio` implements `asyncio.shield`_.
By using `asyncio.shield` while calling `cleanup_resource`, we can rewrite
`do_work`:

.. code:: python

    async def do_work():
        resource = await create_resource()
        try:
            ...  # utilize resource to do some work
        finally:
            await asyncio.shield(cleanup_resource(resource))

.. note::

    Because of additional complexity, this example simplifies correct
    usage of `asyncio.shield` which mandates keeping of task reference,
    thus preventing task garbage collection. In case of cancelling task
    while awaiting `asyncio.shield`, if reference to shielded task is not kept,
    its execution can be interrupted.

Now, once `cleanup_resource` is called, it will not be interrupted. But, even
though `cleanup_resource` is shielded, task executing `do_work` is not
shielded. `await asyncio.shield` is not different from any other
`await` and will result in raising of `CancelledError` if task is canceled.
This behavior doesn't align with assumption of internal resource encapsulation
because `do_work` can finish execution before resource is released.

In order to handle this problem, library `hat-aio` implements
`hat.aio.uncancellable`_. This coroutine can be used
as means of temporary suppressing/delaying cancellation, while shielded
coroutine is executing.

By replacing `asyncio.shield` with `hat.aio.uncancellable`, `do_work`
can guarantee that internal resource is released when `do_work` itself finishes
execution:

.. code:: python

    async def do_work():
        resource = await create_resource()
        try:
            ...  # utilize resource to do some work
        finally:
            await hat.aio.uncancellable(cleanup_resource(resource))

This implementation will stop propagation of `CancelledError` to
`cleanup_resource` and enable uninterrupted execution of `do_work` while
cleanup procedure is running.

When `hat.aio.uncancellable` is used, following constraints should be taken
into account:

* `hat.aio.uncancellable` spawn new task (same as `asyncio.shield`), thus
  introducing additional overhead

* re-raising of `CancelledError` is prioritized over shielded task's
  result/exception (future versions of `hat-aio` could utilize
  `exception groups`_ to prevent suppression of task exceptions in case of
  `CancelledError`)

.. note::

    In majority of cases, `hat.aio.uncancellable` should be called with default
    ``raise_cancel=True`` which, instead of discarding `CancelledError`, delays
    raising of possible `CancelledError` after shielded task finishes execution.


Spawning tasks
--------------

Python `asyncio` library represents concurrent execution threads with
`asyncio.Task` abstraction (this should not be confused with operating system
level threads which enable parallelism). Managing this kind of resources
should be done with additional care, taking into account task's lifetime
and possibility of cancellation. `asyncio` library doesn't provide enough
mechanisms regarding management of multiple tasks and their lifetime.

.. note::

    CPython 3.11 introduced `task groups`_ which support managing lifetime
    of multiple tasks. Although simple grouping of tasks is supported,
    guaranties regarding task cancellation or waiting for resource cleanup
    are not available.

To simplify referencing multiple tasks and control their lifetime, `hat-aio`
implements `hat.aio.Group`_. By spawning tasks via `hat.aio.Group`,
tasks' lifetime is managed by group's lifetime. Together with control of
directly spawned tasks, each group can control lifetime of other groups
(referred to as subgroups or child groups).

Each instance of `hat.aio.Group` transitions between 3 distinctive states:
``OPEN``, ``CLOSING`` and ``CLOSED``. To check for current state and
initiate/wait for state transition, following interface is exposed:

.. code:: python

    @property
    def is_open(self) -> bool:
        ...

    @property
    def is_closing(self) -> bool:
        ...

    @property
    def is_closed(self) -> bool:
        ...

    async def wait_closing(self):
        ...

    async def wait_closed(self):
        ...

    def close(self):
        ...

    async def async_close(self):
        ...

When new instance of group is created, it is initially set to ``OPEN`` state.
Once `close` method is called, group transitions to ``CLOSING`` state.
This state remains active until all associated tasks have finished their
execution and all associated subgroups have transition to ``CLOSED`` state.
Only when all other managed resources (tasks and subgroups) have been
released, instance of group will transition to ``CLOSED`` state. For each group
instance, this state transition (``OPEN`` -> ``CLOSING`` -> ``CLOSED``) is
irreversible. Only first call to `close` method initiates closing of group,
while subsequent call have no effect. Additional `async_close` method
is helper coroutine which calls `close` method and waits for `wait_closed`
coroutine to finish.

To create new tasks or subgroups, `hat.aio.Group` implements following
interface:

.. code:: python

    def create_subgroup(self, log_exceptions: bool | None = None) -> Group:
        ...

    def wrap(self, obj: Awaitable) -> asyncio.Task:
        ...

    def spawn(self, fn: Callable[..., Awaitable], *args, **kwargs) -> asyncio.Task:
        ...

Methods `spawn` and `wrap` create new tasks, associated with group, only
if group is in ``OPEN`` state. If group is in ``CLOSING`` or ``CLOSED`` state,
this methods, including `create_subgroup` method, will raise exception.
If new task is created by referencing coroutine, `spawn` method is preferred
to `wrap` method (spawn method will not create coroutine object instance
if group is not in ``OPEN`` state).

When group's `close` method is called, all associated tasks, that have not
finished their execution, are canceled and all associated subgroups are
closed. Because methods `spawn` and `wrap` return shielded tasks, closing
of group is only external method of requesting task cancellation (under
assumption that reference to task is not obtained by `asyncio` utility methods
such as `asyncio.current_task`).

Implementation of `hat.aio.Group` provides following guarantees:

* only open group can spawn new tasks or create new subgroups

* closing of group will cancel all running tasks and closes all running
  subgroups

* tasks created by `spawn`/`wrap` will be cancelled at most once

* once group is closed, all associated tasks are `done` and all associated
  subgroups are closed

* during closing of group, cancelling running tasks is scheduled for execution
  in event loop thus giving opportunity to all previously created tasks to
  start executing their associated code

To provide described behavior, group depends on following assumptions:

* tasks spawned by group should never suppress propagation of `CancelledError`
  (propagation can be temporary delayed with execution of cleanup procedures or
  means such as `hat.aio.uncancellable`, but each task, once cancelled, must
  finish its execution in near future).

* tasks spawned by group should be referenced only by returned value of
  `spawn`/`wrap` (shielded task)


Resource lifetime
-----------------

Usually, during its lifetime, resource transitions following major states::

    CREATING/OPENING -> CREATED/OPENED -> DESTROYING/CLOSING -> DESTROYED/CLOSED

where some of the resources do not have need for transitional states
`CREATING/OPENING` and/or `DESTROYING/CLOSING`.

If we assume that transition between this states is irreversible, lifetime of
created resource can be modeled with lifetime of associated group. By pairing
single resource instance with single group instance, current group state can
represent current associated resource state.

`hat-aio` library provides `hat.aio.Resource`_ abstract base class that can be
used for associating resource with group:

.. code:: python

    class Resource(abc.ABC):

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await self.async_close()

        @property
        @abc.abstractmethod
        def async_group(self) -> 'Group':
            """Group controlling resource's lifetime."""

        @property
        def is_open(self) -> bool:
            return self.async_group.is_open

        @property
        def is_closing(self) -> bool:
            return self.async_group.is_closing

        @property
        def is_closed(self) -> bool:
            return self.async_group.is_closed

        async def wait_closing(self):
            await self.async_group.wait_closing()

        async def wait_closed(self):
            await self.async_group.wait_closed()

        def close(self):
            self.async_group.close()

        async def async_close(self):
            await self.async_group.async_close()

When using this class, resource should be modeled with class inheriting
`hat.aio.Resource` and defining unimplemented `async_group` property.
Instance of group returned by this property will be used as associated group
which state is mirrored to resource's state.


Examples of resource modeling
-----------------------------

As additional help with `hat.aio.Resource` usage, `hat-aio` implements utility
functions:

* `hat.aio.call_on_cancel`_

  Coroutine which pauses execution of associated task until task is canceled.
  Once task is canceled, function or coroutine passed to
  `hat.aio.call_on_cancel` as argument will be executed.

* `hat.aio.call_on_done`_

  Coroutine which pauses execution of associated task until provided awaitable
  is done. Once awaitable is done, function or coroutine passed to
  `hat.aio.call_on_done` as argument will be executed.

Together with these utility function, `hat.aio.Resource` can be used to model
wide range of idioms, such as:

#. User defined resource with new group instance

    .. code:: python

        class UserResource(hat.aio.Resource):

            @staticmethod
            async def create() -> 'UserResource':
                resource = UserResource()
                resource._async_group = hat.aio.Group()

                ...  # initialize/create resource

                return resource

            @property
            def async_group(self):
                return self._async_group

   In this simple example, resource is associated with newly created group.
   Because `UserResource` inherits `hat.aio.Resource`, all of the lifetime
   associated methods/properties from `hat.aio.Group` are also available
   in `UserResource`. Beside inherited methods/properties, `UserResource`
   can implement its own custom functionality and utilize associated group
   to spawn tasks controlled by resources lifetime.

#. Resource wrapping other resource

    .. code:: python

        class UserResource(hat.aio.Resource):

            @staticmethod
            async def create(other_resource: hat.aio.Resource) -> 'UserResource':
                resource = UserResource()
                resource._other_resource = other_resource

                ...  # initialize/create resource

                return resource

            @property
            def async_group(self):
                return self._other_resource.async_group

   Resources can be bound to groups that are not created during resource
   initialization. Usage of this functionality can be seen when resource
   wraps other resource and associate its lifetime with same group that
   is used for modeling other resource's state. Example of this behavior
   is common in modeling multi layered protocols, where higher level
   of abstraction is directly impacted with lifetime of lower level of
   abstraction.

#. Calling cleanup procedures

    .. code:: python

        class UserResource(hat.aio.Resource):

            @staticmethod
            async def create() -> 'UserResource':
                resource = UserResource()
                resource._async_group = hat.aio.Group()

                ...  # initialize/create resource

                resource.async_group.spawn(hat.aio.call_on_cancel, self._cleanup)

                return resource

            @property
            def async_group(self):
                return self._async_group

            async def _cleanup(self):
                ...  # cleanup

   By spawning `hat.aio.call_on_cancel` as new task, execution of cleanup code
   can be delayed to resource closing. Because this code is run during
   group's ``CLOSING`` state, cleanup code should preform only necessary
   operations and finish execution in short time.

    .. note::

        Under assumption that execution of cleanup code will terminate,
        suppression of `CancelledError` in this case will not have negative
        impact on group's behavior (`call_on_cancel`/`_cleanup` are called
        as topmost coroutines for new task so propagation of `CancelledError`
        in this case is not mandatory).

#. Binding lifetime of one resource to other without sharing group

    .. code:: python

        async def create_resource() -> hat.aio.Resource:
            ...  # create resource

        resource1 = await create_resource()
        resource2 = await create_resource()

        resource1.async_group.spawn(hat.aio.call_on_cancel, resource2.async_close)
        resource1.async_group.spawn(hat.aio.call_on_done, resource2.wait_closing(), resource1.close)

   In this example, first spawn guaranties that `resource1` will not be closed
   until `resource2` is closed. Second spawn initiates closing of `resource1`
   once closing of `resource2` is detected.

#. Associate background task to resource's lifetime

    .. code:: python

        class UserResource(hat.aio.Resource):

            @staticmethod
            async def create() -> 'UserResource':
                resource = UserResource()
                resource._async_group = hat.aio.Group()

                ...  # initialize/create resource

                resource.async_group.spawn(resource._run)

                return resource

            @property
            def async_group(self):
                return self._async_group

            async def _run(self):
                try:
                    ...  # background task's code (usually some kind of loop)

                finally:
                    self.close()

   Tasks spawned by group can be short lived or long lived. Some resources
   have need to execute code during whole resource active lifetime and
   termination of that code's execution should close resource.


Conclusion
----------

Based on previous analysis, Python programs utilizing coroutines and `asyncio`
library should take into account following recommendations:

* coroutines should follow similar best practices as regular functions in
  regard of resource management

* functions/coroutines should ensure resource cleanup for resources
  not crossing function execution boundaries (which are not exposed as part
  of function/coroutine interface) and thus prevent "resource leaks"

* management of resources and ownership rules should be well documented for
  each occurrence of resource as part of input arguments or return values

* each `await` is potential exit point that should be taken into account
  from resource management perspective

* `asyncio` tasks are resources which must be managed the same as other
  resources (e.g. file descriptors)

* execution of resource cleanup procedures is important part of resource
  management which should be correctly encapsulated for internal resources

* `hat.aio.uncancellable` can be used to shield tasks from cancellation
  and temporary delay raising of `CancelledError` in cancelled task

* `hat.aio.Group` can control lifetime of tasks execution and provide
  associated resource (tasks or subgroups) cleanup

* `hat.aio.Resource` can be used to model resource with lifetime defined
  by associated `hat.aio.Group` instance

Usage of `hat-aio` is one of possible ways to tackle resource management
problems. Alternative solutions should also be taken into account
(e.g. `Trio`_).


.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _hat-aio: https://hat-aio.hat-open.com
.. _asyncio.Future: https://docs.python.org/3/library/asyncio-future.html#future-object
.. _asyncio.Task: https://docs.python.org/3/library/asyncio-task.html#asyncio.Task
.. _task cancellation: https://docs.python.org/3/library/asyncio-task.html#task-cancellation
.. _asyncio.shield: https://docs.python.org/3/library/asyncio-task.html#asyncio.shield
.. _hat.aio.uncancellable: https://hat-aio.hat-open.com/py_api/hat/aio.html#uncancellable
.. _exception groups: https://docs.python.org/3/library/exceptions.html#lib-exception-groups
.. _task groups: https://docs.python.org/3/library/asyncio-task.html#task-groups
.. _hat.aio.Group: https://hat-aio.hat-open.com/py_api/hat/aio.html#Group
.. _hat.aio.Resource: https://hat-aio.hat-open.com/py_api/hat/aio.html#Resource
.. _hat.aio.call_on_cancel: https://hat-aio.hat-open.com/py_api/hat/aio.html#call_on_cancel
.. _hat.aio.call_on_done: https://hat-aio.hat-open.com/py_api/hat/aio.html#call_on_done
.. _Trio: https://trio.readthedocs.io
