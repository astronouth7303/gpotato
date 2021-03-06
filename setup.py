#!/usr/bin/env python

from setuptools import setup
import sys

setup(
    name='gpotato',
    version='0.1',
    description='GLib event loop for tulip (PEP 3156)',
    author='Jamie Bliss',
    author_email='astronouth7303@gmail.com',
    license='Apache 2.0',
    url='https://github.com/astronouth7303/gpotato',
    packages=['gpotato'],
    data_files=['README.md', 'examples/test-gtk.py'],
    install_requires=['asyncio'] if sys.version_info < (3,4) else [],
    long_description="""gpotato is a python library that implements a PEP 3156 interface for the GLib main event loop. It is designed to be used together with the tulip reference implementation.

This is a work in progress. The code is experimental and may break at any time.
""",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        ],
    setup_require=["nose"]
)
