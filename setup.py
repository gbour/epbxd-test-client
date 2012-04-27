#!/usr/bin/env python
# -*- coding: utf8 -*-
__license__ = """
  ePBXd test client
    Copyright (C) 2012, Guillaume Bour <guillaume@bour.cc>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, version 3.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
__author__  = "Guillaume Bour <guillaume@bour.cc>"

import subprocess
from setuptools import setup, Command

setup(
    name         = 'epbxd-test-client',
    version      = '0.1.0',
    description  = 'SIP client for the purpose of testing ePBXd software',
    author       = 'Guillaume Bour',
    author_email = 'guillaume@bour.cc',
    url          = 'http://devedge.bour.cc/wiki/epbxd',
    download_url = 'http://devedge.bour.cc/resources/epbxd/src/epbxd-test-client.latest.tar.gz',
    license      = 'GNU General Public License v3',
    classifiers  = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Natural Language :: French',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Communications',
    ],

    long_description = """epbxd-test-client helps sending and tracing SIP and RTP messages.
 It has been written to ease development and ebugging of ePBXd software.
    """,

    scripts=['bin/epbxdclient'],
    packages=['sip'],
    data_files=[
        ('share/doc/python-epbxdclient', ('README.md','AUTHORS','COPYING', 'etc/epbxdclient.yml')),
        ('etc', ('etc/epbxdclient.yml',)),
        ('var/lib/epbxdclient/patterns', ('etc/patterns/ack', 'etc/patterns/invite', 'etc/patterns/ok', 'etc/patterns/ringing')),
    ],
)
