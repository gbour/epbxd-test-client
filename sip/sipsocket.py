#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
    ePBXd test client
    Copyright (C) 2012, Guillaume Bour <guillaume@bour.cc>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, version 3.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
__author__  = "Guillaume Bour <guillaume@bour.cc>"

import socket
import asyncore as async

class SipSocket(async.dispatcher): #_with_send):
    def __init__(self, sock=None, host=None, port=5060, callback=None, data=None, mode='tcp'):
        #async.dispatcher_with_send.__init__(self, sock)
        async.dispatcher.__init__(self, sock)

        self.callback = callback
        self.data     = data

        if sock is None:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM if mode == 'tcp' else
                    socket.SOCK_DGRAM)
            self.connect((host,port))

        self.getsockname = self.socket.getsockname
        self.getpeername = self.socket.getpeername

    def handle_close(self):
        print self.addr, ":closing"
        self.close()

    def handle_read(self):
        raw = self.recv(8192)

        if self.callback is None:
            print "no callback defined on %s" % (self.getsockname()); return

        self.callback(self, raw, self.data)

    def __repr__(self):
        return "SipSocket(%s:%d)" % self.getsockname()


class SipServer(async.dispatcher):
    def __init__(self, callback=None, mode='tcp', data=None):
        async.dispatcher.__init__(self)
        self.callback = callback
        self.data     = data

        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM if mode == 'udp' else socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('localhost', 0))

        if mode != 'udp':
            print 'listen'
            self.listen(5)

    def handle_accept(self):
        pair = self.accept()
        if pair is None:
            return

        sock, addr = pair
        handler = SipSocket(sock, callback=self.callback, data=data)

    def portnum(self):
        return self.socket.getsockname()[1]

    def handle_read(self):
        raw = self.recv(8192)

        if self.callback is None:
            print "no callback defined on %s" % (self.getsockname()); return

        self.callback(self, raw, self.data)

