#!/usr/bin/env python
# -*- coding: utf8 -*-

import socket
import asyncore as async

class SipSocket(async.dispatcher): #_with_send):
    def __init__(self, sock=None, host=None, port=5060, callback=None):
        #async.dispatcher_with_send.__init__(self, sock)
        async.dispatcher.__init__(self, sock)

        self.callback = callback
        if sock is None:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
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

        self.callback(self, raw)


class SipServer(async.dispatcher):
    def __init__(self, callback=None, mode='tcp'):
        async.dispatcher.__init__(self)
        self.callback = callback

        self.create_socket(socket.AF_INET, 
                socket.SOCK_DGRAM if mode == 'udp' else socket.SOCK_STREAM)
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
        handler = SipSocket(sock, callback=self.callback)

    def portnum(self):
        return self.socket.getsockname()[1]

    def handle_read(self):
        raw = self.recv(8192)

        if self.callback is None:
            print "no callback defined on %s" % (self.getsockname()); return

        self.callback(self, raw)


