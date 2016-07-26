#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension
import numpy

version = '1.0.0'

requires = []

setup(
    name='game_loop',
    packages=['game_loop'],
    install_requires=requires,
    license='MIT',
    version=version,
)