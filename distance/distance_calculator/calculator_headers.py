### Calculator Headers
"""
Copyright (c) 2017 Dependable Systems Laboratory, EPFL

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import collections
import functools
import argparse
from pathlib import Path

MAX_DISTANCE = float((1 << 31) - 1)
SMALL_MAX_DISTANCE = float((1 << 31) - 3)
UNSURE_DISTANCE = float(-1.0)

INNER_CALL_DIST_DELTA = 2.0
INTRA_CALL_DIST_COEF = 10.0


class memoize:
    """
    Memoize dectorator.

    Caches a function's return value each time it is called. If called later
    with the same arguments, the cache value is returned (not reevaluated).

    Taken from https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize

    Taken from https://github.com/S2E/s2e-env/blob/master/s2e_env/utils/memoize.py
    """

    def __init__(self, func):
        self._func = func
        self._cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.abc.Hashable):
            return self._func(args)

        if args in self._cache:
            return self._cache[args]

        value = self._func(*args)
        self._cache[args] = value
        return value

    def __repr__(self):
        # Return the function's docstring
        return self._func.__doc__

    def __get__(self, obj, objtype):
        # Support instance methods
        return functools.partial(self.__call__, obj)


def is_path_to_filepath(path):
    """Returns Path object when path is an existing file"""
    p = Path(path)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"'{p}' doesn't exist")
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"'{p}' is not a file")
    return p


def is_path_to_dir(path):
    """Returns Path object when path is an existing directory"""
    p = Path(path)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"'{p}' doesn't exist")
    if not p.is_dir():
        raise argparse.ArgumentTypeError(f"'{p}' is not a directory")
    return p
