"""This module includes tests of the code object representation.

>>> def f(x):
...     def g(y):
...         return x + y
...     return g
...

>>> dump(f.__code__)
name: f
argcount: 1
posonlyargcount: 0
kwonlyargcount: 0
varnames: ('x', 'g')
cellvars: ('x',)
freevars: ()
nlocals: 2
flags: 3
consts: ('None', "'f'", '<code object g>')

>>> dump(f(4).__code__)
name: g
argcount: 1
posonlyargcount: 0
kwonlyargcount: 0
varnames: ('y', 'x')
cellvars: ()
freevars: ('x',)
nlocals: 2
flags: 19
consts: ('None', "'f.<locals>.g'")

>>> def h(x, y):
...     a = x + y
...     b = x - y
...     c = a * b
...     return c
...

>>> dump(h.__code__)
name: h
argcount: 2
posonlyargcount: 0
kwonlyargcount: 0
varnames: ('x', 'y', 'a', 'b', 'c')
cellvars: ()
freevars: ()
nlocals: 5
flags: 3
consts: ('None', "'h'")

>>> def attrs(obj):
...     print(obj.attr1)
...     print(obj.attr2)
...     print(obj.attr3)

>>> dump(attrs.__code__)
name: attrs
argcount: 1
posonlyargcount: 0
kwonlyargcount: 0
varnames: ('obj',)
cellvars: ()
freevars: ()
nlocals: 1
flags: 3
consts: ('None', "'attrs'", "'print'", "'attr1'", "'attr2'", "'attr3'")

>>> def optimize_away():
...     'doc string'
...     'not a docstring'
...     53
...     0x53

>>> dump(optimize_away.__code__)
name: optimize_away
argcount: 0
posonlyargcount: 0
kwonlyargcount: 0
varnames: ()
cellvars: ()
freevars: ()
nlocals: 0
flags: 3
consts: ("'doc string'", "'optimize_away'", 'None')

>>> def keywordonly_args(a,b,*,k1):
...     return a,b,k1
...

>>> dump(keywordonly_args.__code__)
name: keywordonly_args
argcount: 2
posonlyargcount: 0
kwonlyargcount: 1
varnames: ('a', 'b', 'k1')
cellvars: ()
freevars: ('k1',)
nlocals: 3
flags: 3
consts: ('None', "'keywordonly_args'")

>>> def posonly_args(a,b,/,c):
...     return a,b,c
...

>>> dump(posonly_args.__code__)
name: posonly_args
argcount: 3
posonlyargcount: 2
kwonlyargcount: 0
varnames: ('a', 'b', 'c')
cellvars: ()
freevars: ()
nlocals: 3
flags: 3
consts: ('None', "'posonly_args'")

"""

import inspect
import sys
import threading
import unittest
import weakref
import opcode
import gc
try:
    import ctypes
except ImportError:
    ctypes = None
from test.support import (run_doctest, run_unittest, cpython_only,
                          check_impl_detail)


def consts(t):
    """Yield a doctest-safe sequence of object reprs."""
    for elt in t:
        r = repr(elt)
        if r.startswith("<code object"):
            yield "<code object %s>" % elt.co_name
        else:
            yield r

def dump(co):
    """Print out a text representation of a code object."""
    for attr in ["name", "argcount", "posonlyargcount",
                 "kwonlyargcount", "varnames",
                 "cellvars", "freevars", "nlocals", "flags"]:
        print("%s: %s" % (attr, getattr(co, "co_" + attr)))
    print("consts:", tuple(consts(co.co_consts)))

# Needed for test_closure_injection below
# Defined at global scope to avoid implicitly closing over __class__
def external_getitem(self, i):
    return f"Foreign getitem: {super().__getitem__(i)}"

class CodeTest(unittest.TestCase):

    @cpython_only
    def test_newempty(self):
        import _testcapi
        co = _testcapi.code_newempty("filename", "funcname", 15)
        self.assertEqual(co.co_filename, "filename")
        self.assertEqual(co.co_name, "funcname")
        self.assertEqual(co.co_firstlineno, 15)

    @cpython_only
    @unittest.skip("sgross: can't add freevars")
    def test_closure_injection(self):
        # From https://bugs.python.org/issue32176
        from types import FunctionType

        def create_closure(__class__):
            return (lambda: __class__).__closure__

        def new_code(c):
            '''A new code object with a __class__ cell added to freevars'''
            return c.replace(co_freevars=c.co_freevars + ('__class__',))

        def add_foreign_method(cls, name, f):
            code = new_code(f.__code__)
            assert not f.__closure__
            closure = create_closure(cls)
            defaults = f.__defaults__
            setattr(cls, name, FunctionType(code, globals(), name, defaults, closure))

        class List(list):
            pass

        add_foreign_method(List, "__getitem__", external_getitem)

        # Ensure the closure injection actually worked
        function = List.__getitem__
        class_ref = function.__closure__[0].cell_contents
        self.assertIs(class_ref, List)

        # Ensure the code correctly indicates it accesses a free variable
        self.assertFalse(function.__code__.co_flags & inspect.CO_NOFREE,
                         hex(function.__code__.co_flags))

        # Ensure the zero-arg super() call in the injected method works
        obj = List([1, 2, 3])
        self.assertEqual(obj[0], "Foreign getitem: 1")

    def test_constructor(self):
        def func(): pass
        co = func.__code__
        CodeType = type(co)

        # test code constructor
        return CodeType(co.co_argcount,
                        co.co_posonlyargcount,
                        co.co_kwonlyargcount,
                        co.co_nlocals,
                        co.co_framesize,
                        co.co_ndefaultargs,
                        co.co_nmeta,
                        co.co_flags,
                        co.co_code,
                        co.co_consts,
                        co.co_varnames,
                        co.co_filename,
                        co.co_name,
                        co.co_firstlineno,
                        co.co_lnotab,
                        co.co_exc_handlers,
                        co.co_freevars,
                        co.co_cellvars,
                        co.co_free2reg,
                        co.co_cell2reg)

    def test_replace(self):
        def func():
            x = 1
            return x
        code = func.__code__

        # different co_name, co_varnames, co_consts
        def func2():
            y = 2
            return y
        code2 = func2.__code__

        for attr, value in (
            ("co_argcount", 0),
            ("co_posonlyargcount", 0),
            ("co_kwonlyargcount", 0),
            ("co_nlocals", 0),
            ("co_framesize", 0),
            ("co_flags", code.co_flags | inspect.CO_COROUTINE),
            ("co_firstlineno", 100),
            ("co_code", code2.co_code),
            ("co_consts", code2.co_consts),
            ("co_varnames", code2.co_varnames),
            ("co_freevars", ("freevar",)),
            ("co_cellvars", ("cellvar",)),
            ("co_filename", "newfilename"),
            ("co_name", "newname"),
            ("co_lnotab", code2.co_lnotab),
        ):
            with self.subTest(attr=attr, value=value):
                new_code = code.replace(**{attr: value})
                self.assertEqual(getattr(new_code, attr), value)


def isinterned(s):
    return s is sys.intern(('_' + s + '_')[1:-1])

class CodeConstsTest(unittest.TestCase):

    def find_const(self, consts, value):
        for v in consts:
            if v == value:
                return v
        self.assertIn(value, consts)  # raises an exception
        self.fail('Should never be reached')

    def assertIsInterned(self, s):
        if not isinterned(s):
            self.fail('String %r is not interned' % (s,))

    @cpython_only
    def test_interned_string(self):
        co = compile('res = "str_value"', '?', 'exec')
        v = self.find_const(co.co_consts, 'str_value')
        self.assertIsInterned(v)

    @cpython_only
    def test_interned_string_in_tuple(self):
        co = compile('res = ("str_value",)', '?', 'exec')
        v = self.find_const(co.co_consts, ('str_value',))
        self.assertIsInterned(v[0])

    @cpython_only
    def test_interned_string_in_frozenset(self):
        co = compile('res = a in {"str_value"}', '?', 'exec')
        v = self.find_const(co.co_consts, frozenset(('str_value',)))
        self.assertIsInterned(tuple(v)[0])

    @cpython_only
    def test_interned_string_default(self):
        def f(a='str_value'):
            return a
        self.assertIsInterned(f())


class CodeWeakRefTest(unittest.TestCase):

    def test_basic(self):
        # Create a code object in a clean environment so that we know we have
        # the only reference to it left.
        namespace = {}
        exec("def f(): pass", globals(), namespace)
        f = namespace["f"]
        del namespace

        self.called = False
        def callback(code):
            self.called = True

        # f is now the last reference to the function, and through it, the code
        # object.  While we hold it, check that we can create a weakref and
        # deref it.  Then delete it, and check that the callback gets called and
        # the reference dies. We need a gc call because code objects now use
        # deferred reference counting to avoid contention on reference counts
        # when accessed by multiple threads.
        coderef = weakref.ref(f.__code__, callback)
        self.assertTrue(bool(coderef()))
        del f
        gc.collect()
        self.assertFalse(bool(coderef()))
        self.assertTrue(self.called)


if check_impl_detail(cpython=True) and ctypes is not None:
    py = ctypes.pythonapi
    freefunc = ctypes.CFUNCTYPE(None,ctypes.c_voidp)

    RequestCodeExtraIndex = py._PyEval_RequestCodeExtraIndex
    RequestCodeExtraIndex.argtypes = (freefunc,)
    RequestCodeExtraIndex.restype = ctypes.c_ssize_t

    SetExtra = py._PyCode_SetExtra
    SetExtra.argtypes = (ctypes.py_object, ctypes.c_ssize_t, ctypes.c_voidp)
    SetExtra.restype = ctypes.c_int

    GetExtra = py._PyCode_GetExtra
    GetExtra.argtypes = (ctypes.py_object, ctypes.c_ssize_t,
                         ctypes.POINTER(ctypes.c_voidp))
    GetExtra.restype = ctypes.c_int

    LAST_FREED = None
    def myfree(ptr):
        global LAST_FREED
        LAST_FREED = ptr

    FREE_FUNC = freefunc(myfree)
    FREE_INDEX = RequestCodeExtraIndex(FREE_FUNC)

    class CoExtra(unittest.TestCase):
        def get_func(self):
            # Defining a function causes the containing function to have a
            # reference to the code object.  We need the code objects to go
            # away, so we eval a lambda.
            return eval('lambda:42')

        def test_get_non_code(self):
            f = self.get_func()

            self.assertRaises(SystemError, SetExtra, 42, FREE_INDEX,
                              ctypes.c_voidp(100))
            self.assertRaises(SystemError, GetExtra, 42, FREE_INDEX,
                              ctypes.c_voidp(100))

        def test_bad_index(self):
            f = self.get_func()
            self.assertRaises(SystemError, SetExtra, f.__code__,
                              FREE_INDEX+100, ctypes.c_voidp(100))
            self.assertEqual(GetExtra(f.__code__, FREE_INDEX+100,
                              ctypes.c_voidp(100)), 0)

        def test_free_called(self):
            # Verify that the provided free function gets invoked
            # when the code object is cleaned up.
            f = self.get_func()

            SetExtra(f.__code__, FREE_INDEX, ctypes.c_voidp(100))
            del f
            gc.collect()
            self.assertEqual(LAST_FREED, 100)

        def test_get_set(self):
            # Test basic get/set round tripping.
            f = self.get_func()

            extra = ctypes.c_voidp()

            SetExtra(f.__code__, FREE_INDEX, ctypes.c_voidp(200))
            # reset should free...
            SetExtra(f.__code__, FREE_INDEX, ctypes.c_voidp(300))
            self.assertEqual(LAST_FREED, 200)

            extra = ctypes.c_voidp()
            GetExtra(f.__code__, FREE_INDEX, extra)
            self.assertEqual(extra.value, 300)
            del f

        def test_free_different_thread(self):
            import gc
            # Freeing a code object on a different thread then
            # where the co_extra was set should be safe.
            f = self.get_func()
            class ThreadTest(threading.Thread):
                def __init__(self, f, test):
                    super().__init__()
                    self.f = f
                    self.test = test
                def run(self):
                    self.f = None
                    gc.collect()
                    self.test.assertEqual(LAST_FREED, 500)

            SetExtra(f.__code__, FREE_INDEX, ctypes.c_voidp(500))
            tt = ThreadTest(f, self)
            del f
            tt.start()
            tt.join()
            self.assertEqual(LAST_FREED, 500)


def test_main(verbose=None):
    from test import test_code
    run_doctest(test_code, verbose)
    tests = [CodeTest, CodeConstsTest, CodeWeakRefTest]
    if check_impl_detail(cpython=True) and ctypes is not None:
        tests.append(CoExtra)
    run_unittest(*tests)

if __name__ == "__main__":
    test_main()
