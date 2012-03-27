#!/usr/bin/env python
# -*- coding: utf8 -*-

from sip import SipServer

class Account(object):
    def __init__(self, username, domain, port=5060):
        self.username = username
        self.domain   = domain
        self.port     = port

        # open client port
        self.sips     = SipServer()

        self._register = 'none'
        self._cseq = self.__cseq__()

    def set_manager(self, m):
        self._m = m

    def __cseq__(self):
        """Sequence generator
        """
        cseq = 0

        while True:
            cseq += 1
            yield cseq

    def do_status(self, *args):
        self._m.repl.echo("%s account:\n . registration= %s" % (self.username, self._register))

    def do_register(self, *args):
        self._m.repl.echo("Registering %s" % self.username)

        def response(callid, response):
            if   response.status == 200:
                self._register = 'ok'
                self._m.repl.echo("%s registration successful" % self.username)
            elif response.status == 401:
                self._register = 'unauthorized'
                self._m.repl.echo("%s registration failed (unauthorized)" % self.username)

        callid = self._m.do_request('REGISTER', (self.domain, self.port), {
            'cseq'       : self._cseq.next(),
            'local_ip'   : 'localhost',
            'local_port' : self.sips.portnum(),
            'local_user' : self.username,
            'remote_user': self.username,
        }, response)

        self._register = 'pending'

    def do_dial(self, *args):
        self._m.repl.echo("Dialing %s" % args[0])

        def response(callid, resp):
            if   resp.status == 404:
                self._m.repl.echo("Target %s not found" % args[0])
            elif resp.status == 100: # Trying
                pass


        callid = self._m.do_request('INVITE', (self.domain, self.port), {
            'cseq'       : self._cseq.next(),
            'local_ip'   : 'localhost',
            'local_port' : self.sips.portnum(),
            'local_user' : self.username,
            'remote_user': args[0]
        }, response)

