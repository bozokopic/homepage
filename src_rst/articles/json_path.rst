JSON Path
=========

Today, `JSON <http://www.json.org>`_ is widely used format for representing
data structures. Together with encoding/decoding rules, it specifies
data types which are supported by most of modern programming languages and
platforms.

JSON Path provides basic functions for referencing and manipulating
deeply nested JSON data structure.

`Hat Open <https://hat-open.com>`_ provides libraries implementing
this functionality:

    * Python - `hat-json <https://github.com/hat-open/hat-json>`_
    * JavaScript - `@hat-open/util <https://github.com/hat-open/hat-util>`_


Definitions
-----------

Following definitions describe JSON Data, JSON Path and operations
based on these data types. Mathematical notation is used only as
"neutral" tool to describe data structures and operations without
usage of any particular programming language or paradigm. Definitions
themselves are not strict - they should be taken as guidelines to
implementation of JSON Path libraries.


Data
''''

JSON Data types can be defined as set :math:`Data`:

.. math::

    Data = Constant \cup Number \cup String \cup Array \cup Object

where:

* :math:`Constant`

    .. math::

        Constant = \{ null, true, false \}

    Constant values represented with literals ``null``, ``true`` and ``false``.

* :math:`Number`

    .. math::

        Number = ℝ

    Real numbers (JSON doesn't distinguish between integers and floating point
    values).

* :math:`String`

    .. math::

        String = (c_1, ..., c_n), \quad n \geq 0, \quad
        c_i \in \text{Unicode characters}

    Sequence of zero or more Unicode characters including additional escaped
    sequences.

* :math:`Array`

    .. math::

        Array = (a_1, ..., a_n), \quad n \geq 0, \quad a_i \in Data

    Ordered set of zero or more elements which are themselves JSON Data.

* :math:`Object`

    .. math::

        Object = \{ (k_1, v_1), ..., (k_n, v_n) \}, \quad
        n \geq 0, \quad k_i \in String, \quad v_i \in Data

    Associative sequence of key/value pairs where keys are strings and
    values are one of JSON Data


Path
''''

JSON Path is reference to part of composite JSON data. It is itself
represented as JSON Data and can be defined as set :math:`Path`:

.. math::

    Path = Integer \cup String \cup PArray

where:

.. math::

    Integer &= ℕ_0 \\
    PArray &= (a_1, ..., a_n), \quad n \geq 0, \quad a_i \in Path

In following definitions, we will use operator :math:`\&` as reference to
data and operator :math:`*` as value of referenced data.

Algorithm, used as basis for resolving path references, can be represented
with function :math:`ref`:

.. math::

    ref(data, path) = \begin{cases}
        ref_int(data, path) & path \in Integer \\
        ref_str(data, path) & path \in String \\
        ref_arr(data, path) & path \in PArray
    \end{cases}

where:

.. math::

    data \in Data, \quad path \in Path

Usage of different data types as paths, enables one to reference data in
different data structures:

* :math:`path \in Integer`

    .. math::

        ref_int(data, path) = \begin{cases}
            \&a_{path + 1} & data \in Array, \quad
                                 data = (a_1, ..., a_n), \quad
                                 path < n \\
            \&null & \text{otherwise}
        \end{cases}

    Integer paths are used for referencing elements of array. If
    referenced element doesn't exist or provided data is not an array,
    neutral ``null`` element is referenced.

* :math:`path \in String`

    .. math::

        ref_str(data, path) = \begin{cases}
            \&v_i & data \in Object, \quad
                    data = \{ (k_1, v_1), ..., (k_n, v_n) \}, \quad
                    path = k_i \\
            \&null & \text{otherwise}
        \end{cases}

    String paths reference object entries based on object's key values.
    If referenced key doesn't exist or provided data is not an object,
    neutral ``null`` element is referenced.

* :math:`path \in PArray`

    .. math::

        ref_arr(data, path) = \begin{cases}
            \&data & path = \emptyset \\
            ref(*ref(data, a_1), (a_2, ..., a_n)) & path = (a_1, ..., a_n)
        \end{cases}

    Array paths are used for composition of other paths. Array
    elements are used for recursive path application on result
    of previous path application.


Normalization
'''''''''''''

Each path can be normalized - represented as array of strings and integers:

.. math::

    NPath = (a_1, ..., a_n), \quad n \geq 0, \quad a_i \in Integer \cup String

Path normalization is defined as function :math:`norm`:

.. math::

    & norm : Path \rightarrow NPath \\
    & norm(path) = \begin{cases}
        (path) & path \in Integer \cup String \\
        \emptyset & path \in PArray, \quad
                    path = \emptyset \\
        norm(p_1) \cup norm((p_2, ..., p_n)) & path \in PArray, \quad
                                               path = (p_1, ..., p_n)
    \end{cases}

When used as argument to :math:`ref` function, normalized path is
equivalent to its original non-normalized form:

.. math::

    ref(data, path) = ref(data, norm(path))

These property of normalized path is useful in case of path functions'
implementations. By normalizing path prior to its usage, implementation
or :math:`ref` can be based on sequential reduction of provided data instead
of recursive application.


Functions
'''''''''

* :math:`get`

    .. math::

        & get : Data \times Path \rightarrow Data \\
        & get(data, path) = value

    Function :math:`get` is used for obtaining part of :math:`data` structure
    referenced by :math:`path`.

    Examples::

        data = {"a": [1, 2, {"b": true}, []]}

        get(data, []) = {"a": [1, 2, {"b": true}, []]}
        get(data, "a") = [1, 2, {"b": true}, []]
        get(data, ["a", 0]) = 1
        get(data, ["a", 2, "b"]) = true
        get(data, ["a", [2, ["b"]]]) = true
        get(data, [[], [[]]]) = {"a": [1, 2, {"b": true}, []]}
        get(data, 0) = null
        get(data, "b") = null
        get(data, ["a", 4]) = null

* :math:`set`

    .. math::

        & set : Data \times Path \times Data \rightarrow Data \\
        & set(data, path, value) = data'

    Function :math:`set` is used for creating new data structure :math:`data'`.
    Difference, between :math:`data` and :math:`data'`, is in part of data
    structure referenced by :math:`path`. In :math:`data'` this part is
    replaced with :math:`value`.

    Edge cases:

        * `array index out of bound`

            If integer path references array with length less than path,
            additional ``null`` elements are created so that referenced
            array element can be set to provided value.

        * `object key not available`

            If string path references object which doesn't contain entry
            with key equal to path, new entry is created.

        * `path type doesn't match data type`

            If integer path references data which is not array, data is
            replaced with empty array and previously described `array index out
            of bound` edge case is applied.

            If string path references data which is not object, data is
            replaced with empty object and previously described `object key not
            available` edge case is applied.

    Examples::

        data = {"a": [1, 2, {"b": true}, []]}

        set(data, ["a", 2, "b"], false) = {"a": [1, 2, {"b": false}, []]}
        set(data, "a", 42) = {"a": 42}
        set(data, ["a", [3], 0], 42) = {"a": [1, 2, {"b": true}, [42]]}
        set(data, ["a", [3], 1], 42) = {"a": [1, 2, {"b": true}, [null, 42]]}
        set(data, [], 42) = 42
        set(null, [1, "a", 2], 42) = [null, {"a": [null, null, 42]}]

* :math:`remove`

    .. math::

        & remove : Data \times Path \rightarrow Data \\
        & remove(data, path) = data'

    Function :math:`remove` is used for creating new data structure
    :math:`data'` based on provided :math:`data`. Difference, between
    :math:`data` and :math:`data'`, is in part of data structure referenced
    by :math:`path`. In :math:`data'` this part is omitted.

    Edge cases:

        In edge cases:

            * array index out of bound
            * object key not available
            * path type doesn't match data type

        :math:`data'` is same as :math:`data`.

    Examples::

        data = {"a": [1, 2, {"b": true}, []]}

        delete(data, ["a", 1]) = {"a": [1, {"b": true}, []]}
        delete(data, []) = null
        delete(data, ["a", 2, "b"]) = {"a": [1, 2, {}, []]}
        delete(data, "b") = {"a": [1, 2, {"b": true}, []]}

With this basic functions, other specialized functions can be defined.
Example of commonly used derived function is :math:`change`:

.. math::

    & change : Data \times Path \times (Data \rightarrow Data) \rightarrow Data \\
    & change(data, path, f) = set(data, path, f(get(data, path)))

where :math:`f` is arbitrary data transformation function:

.. math::

    f : Data \rightarrow Data

It should be noted that all of these functions are "pure functions" that
shouldn't make in-place changes of provided data arguments. Implementations
usually take this into account by optimizing re usability of shared data.


Characteristics
---------------

Some of the interesting characteristics of JSON Path approach to JSON Data
referencing are:

* full JSON Data coverage

    Paths enable operations on all kinds of JSON Data without additional
    constrains on structural complexity or used data types.

* get/set operations

    Same path instances can be used for both retrieval and change of referenced
    data. This is result of single path reference resolving algorithm, used
    as basis for get and set implementation.

* flexible path composition

    Support for path normalization provides opportunities for composition
    of multiple path parts into single path.

    Example::

        p1 = [ ..first-path.. ]
        p2 = [ ..second-path.. ]
        p3 = [ ..third-path.. ]

        [p1, p2, p3] ≅ [p1, [p2, [p3]]] ≅ [p1, [p2, p3]] ≅ [[p1, p2], p3]

* safe retrieval of deeply nested optional elements

    In case of complex array paths, if part of referenced data is not
    available, path traversal can be short-circuited without additional
    repetitive checking.

    Example::

        data = {'a': {'b': {'c': 123}}}
        path = ['a', 'd', 'c']
        get(data, path) == null

* JSON Path is subset of JSON Data

    This property enables easy serialization and exchange of paths. Also,
    all path functions can be used for operations on paths themselves.

* implementation simplicity

    With representation of paths as JSON Data and normalization into single
    "flat" array, no additional parsing is required and implementation
    can be based on optimal short-circuited iteration. This enables
    efficient implementations in wide range of modern programming languages
    and platforms.


Python implementation
---------------------

Python implementation of JSON Path functions is available as part of
`hat-json` library.

Function signature is similar to abstract definition of JSON Path
functions. Notable differences are:

    * possibility to define alternative neutral `null` value in case of
      `get` function
    * function `set` is named `set_` to avoid name clash with builtin function

.. code:: python

    Array = typing.List['Data']
    Object = typing.Dict[str, 'Data']
    Data = typing.Union[None, bool, int, float, str, Array, Object]
    Path = typing.Union[int, str, typing.List['Path']]

    def get(data: Data, path: Path, default: typing.Optional[Data] = None) -> Data:
        ...

    def set_(data: Data, path: Path, value: Data) -> Data:
        ...

    def remove(data: Data, path: Path) -> Data:
        ...


JavaScript implementation
-------------------------

JavaScript implementation of JSON Path functions is available as part of
`@hat-open/util` library.

This implementation provides full functionality of JSON Path definition
with some changes to API itself. Most of these changes are made to enable
more functional programming style:

    * all functions are curried
    * `delete` is renamed to `omit`
    * position of arguments are changed

.. code:: javascript

    // get : Path -> Data -> Data
    function get(path, data) {
        // return value
    }

    // change : Path -> (Data -> Data) -> Data
    function change(path, fn, data) {
        // return new data
    }

    // set : Path -> Data -> Data -> Data
    function set(path, value, data) {
        // return new data
    }

    // omit : Path -> Data -> Data
    function omit(path, data) {
        // return new data
    }


Comparison to other JSON Data functions
---------------------------------------

Referencing parts of deeply nested complex JSON Data structures is the well
known problem. There exists a lot of different applications and libraries
that try to provide a solution to this problem.

To compare previously described JSON Path to alternatives, we can group
other implementations based on some of theirs significant characteristics:

* string based paths

    Some of the libraries use paths encoded as strings. Usually, this
    encodings consist of custom rules that try to mimic
    `XPath <https://en.wikipedia.org/wiki/XPath>`_ or JavaScript notation.

    Main benefit of this approach is condensed path definition which
    is usually well suited for usage as command line arguments to
    applications.

    Drawbacks of this approach are:

        * additional path string decoder
        * variety of custom non-standard notations
        * difficult composition of path segments

    Some of the notable implementations:

        * `JSONPath <https://goessner.net/articles/JsonPath/>`_
        * `jq <https://stedolan.github.io/jq/>`_
        * `lodash <https://lodash.com/>`_ (with limited array based
          composition)

* lenses

    Usage of lens functions if approach popularized by Haskell
    `Lens library <https://hackage.haskell.org/package/lens>`_. It is based
    on functions that can be used as references to parts of composite data.

    Advantage of lenses is mostly associated with functional programming
    style and possibility of lens composition by usage of function
    composition.

    Drawback of this approach are:

        * tightly dependent on specific programming language function
          definitions
        * not appropriate for serialization

    Some of the notable implementations:

        * `ramda.js <https://ramdajs.com/docs/#lens>`_


.. footer::

    Thanks to Jakov Krstulovic Opara for review and suggestions.
