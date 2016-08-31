# -*- coding: utf-8 -*-
from __future__ import print_function
import pyapitest


def test_pyapitest():
    errors, output = pyapitest.run('tests/pyapitest.json')
    print('\n'.join(output))
    assert errors == 0
