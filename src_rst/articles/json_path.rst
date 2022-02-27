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
themselves are not strict "mathematical" definitions.


Data
''''

.. math::

    Data &= Constant \cup
            Number \cup
            String \cup
            JArray \cup
            Object \\
    Constant &= \{ null, true, false \} \\
    Number &= ℝ \\
    JArray &= (a_1, ..., a_n), \quad
              n \geq 0, \quad
              a_i \in Data \\
    Object &= \{ (k_1, v_1), ..., (k_n, v_n) \}, \quad
              n \geq 0, \quad
              k_i \in String, \quad
              v_i \in Data

JSON data types include:

    * Constants

        ``null``, ``true`` and ``false``

    * Numbers

        Real numbers (JSON doesn't distinguish between integers and
        floating point values)

    * Strings

        Sequence of Unicode characters including additional escaped sequences

    * Arrays

        Ordered set of zero or more elements which are themselves JSON data

    * Objects

        Associative sequence of key/value pairs where keys are strings and
        values are one of JSON data


Path
''''

.. math::

    Path &= Integer \cup String \cup PArray, \quad Path \subset Data \\
    Integer &= ℕ_0, \quad Integer \subset Number \\
    PArray &= (a_1, ..., a_n), \quad
              n \geq 0, \quad
              a_i \in Path

JSON Path is subset of JSON data used as reference to "part of" composite
JSON data. If we introduce operator :math:`\&` as reference to data, we
can define function :math:`ref(data, path)` as:

.. math::

    ref(data, path) &= \begin{cases}
        ref_int(data, path) & path \in Integer \\
        ref_str(data, path) & path \in String \\
        ref_arr(data, path) & path \in PArray
    \end{cases} \\
    ref_int(data, path_int) &= \begin{cases}
        \&a_{path_int + 1} & data \in JArray, \quad
                             data = (a_1, ..., a_n), \quad
                             path_int < n \\
        \&null & \text{otherwise}
    \end{cases} \\
    ref_str(data, path_str) &= \begin{cases}
        \&v_i & data \in Object, \quad
                data = \{ (k_1, v_1), ..., (k_n, v_n) \}, \quad
                k_i = path_str \\
        \&null & \text{otherwise}
    \end{cases} \\
    ref_arr(data, path_arr) &= \begin{cases}
        \&data & path_arr = \emptyset \\
        ref(ref(data, a_1), (a_2, ..., a_n)) & path_arr = (a_1, ..., a_n)
    \end{cases} \\
    & data \in Data, \quad
      path \in Path, \quad
      path_int \in Integer, \quad
      path_str \in String, \quad
      path_arr \in PArray \\

Usage of different data types as paths, enables as to reference data in
different data structures:

    * Integer

        Integer paths are used for referencing elements of array. If
        referenced element doesn't exist or provided data is not array,
        neutral ``null`` element is referenced.

    * String

        String paths reference object entries based on object's key values.
        If referenced key doesn't exist or provided data is not object,
        neutral ``null`` element is referenced.

    * Array

        Array paths are used for composition of other paths. Array
        elements are used for recursive path application on result
        of "previous" path application.


Normalization
'''''''''''''

Each path can be normalized - represented as array of strings and integers:

.. math::

    normalize &: Path \rightarrow NPath \\
    normalize(path) &= \begin{cases}
        (path) & path \in Integer \cup String \\
        \emptyset & path \in PArray, \quad
                    path = \emptyset \\
        normalize(p_1) \cup normalize((p_2, ..., p_n)) & path \in PArray, \quad
                                                         path = (p_1, ..., p_n)
    \end{cases} \\
    NPath &= Array(Integer \cup String), \quad NPath \subset Path

When used as argument to :math:`ref` function, normalized path is
equivalent to it's original non-normalized form:

.. math::

    ref(data, path) &= ref(data, normalized(path)), \\
    & data \in Data, \quad path \in Path

These property of normalized path is useful in case of path functions'
implementations. By normalizing path prior to it's usage, implementation
or :math:`ref` can be based on sequential reduction of provided data instead
of recursive application.


Functions
'''''''''

* :math:`get`

    .. math::

        get &: Data \times Path \rightarrow Data \\
        get(data, path) &= value

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

        set &: Data \times Path \times Data \rightarrow Data \\
        set(data, path, value) &= data'

    Function :math:`set` is used for creating new data structure :math:`data'`
    similar to provided :math:`data`. Difference is in part of data
    structure referenced by :math:`path`. In :math:`data'` this part is
    replaced with :math:`value`.

    Edge cases:

        * array index out of bound

            If integer path references array with length less than path,
            additional ``null`` elements are created so that referenced
            array element can be set to provided value.

        * object key not available

            If string path references object which doesn't contain entry
            with key equal to path, new entry is created.

        * path type doesn't match data type

            If integer path references data which is not array, data is
            replaced with empty array after which `array index out of bound`
            edge case is applied.

            If string path references data which is not object, data is
            replaced with empty object after which `object key not available`
            edge case is applied.

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

        remove &: Data \times Path \rightarrow Data \\
        remove(data, path) &= data'

    Function :math:`remove` is used for creating new data structure
    :math:`data'` similar to provided :math:`data`. Difference is in part
    of data structure referenced by :math:`path`. In :math:`data'` this part
    is omitted.

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

    change &: Data \times Path \times (Data \rightarrow Data) \rightarrow Data \\
    change(data, path, f) &= set(data, path, f(get(data, path)))

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
    data.

* flexible composition

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

Problem of referencing (getting/setting) parts of deeply nested complex JSON
Data structures is not a new one. There exists a lot of different applications
and libraries that try to provide a solution to this problem.

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
