#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from setuptools import setup, Extension
except ImportError:
    from distutils.core import setup, Extension

version = '1.0.0'

requires = []

setup(
    name='show_loop',
    packages=['show_loop'],
    install_requires=requires,
    license='MIT',
    version=version,
)