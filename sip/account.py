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

import random, time, os.path
from struct      import *
from collections import namedtuple
from sipsocket   import *

# name and matching RTP type
ENCODINGS = {
    'ulaw': 0,
    'gsm' : 3,
    'alaw': 8,
}

from   collections import namedtuple
Server = namedtuple('Server', ['transport','host','port'])

class Account(object):
    def __init__(self, username, registrar, proxy):
        self.username  = username
        self.registrar = registrar
        self.proxy     = proxy

        # open client port
        # TODO: we should have 2 servers (1 for registrar, 1 for proxy)
        self.sips     = SipServer(self.receive, mode=registrar.transport)

        self._register = 'none'
        self._cseq = self.__cseq__()
        self.transactions = {}
        self.rtp_dump_files = {}
        self.rtp_ports = {}

    def set_manager(self, m):
        self._m = m

    def __cseq__(self):
        """Sequence generator
        """
        cseq = 0

        while True:
            cseq += 1
            yield cseq

    def receive(self, sock, data, extra=None):
        """Receive data from private socket
        """
        self._m.repl.echo("Account %s: receiving incoming message on private socket" % self.username)
        self._m.receive(sock, data, extra)

    def receive_rtp(self, sock, data, callid):
        """Receive RTP data
        """
        self._m.repl.echo("%s: receiving RTP data (callid= %s)" % (self.username, callid))

        Rtp = namedtuple('Rtp', 'version padding exten cc marker ptype sequence timestamp ssrc')
        (pad1, pad2, seq, tstamp, ssrc) = unpack('!ccHII', data[:12])
        pad1 = ord(pad1)
        pad2 = ord(pad2)

        rtp = Rtp._make([
            # version (2 bits)
            pad1 >> 6,
            # padding (1 bit)
            pad1 & 32 >> 5,
            # exten (1 bit)
            pad1 & 16 >> 4,
            # CSRC count (4 bits)
            pad1 & 15,
            # parker (1 bit)
            pad2 >> 7,
            # payload type (7 bits)
            pad2 & 127,

            seq, tstamp, ssrc
        ])

        csrcs = unpack('!' + 'I'*rtp.cc, data[12:12+4*rtp.cc])
        # RTP header
        self._m.repl.echo("%s, csrcs=%s, payload=%d" % 
                (str(rtp), str(csrcs),	(len(data)-12-4*rtp.cc)))

        if callid in self.rtp_dump_files:
            self.rtp_dump_files[callid].write(data[12+4*rtp.cc:])

    def do_status(self, *args):
        """Display account status
        """
        self._m.repl.echo("%s account:\n . registration= %s" % (self.username, self._register))

    def do_register(self, *args):
        """Register account at registrar.
        Send a REGISTER command to the registar, and handle the response.
        Usage: *account-name* register
        """
        self._m.repl.echo("Registering %s" % self.username)

        def response(callid, response):
            if   response.status == 200:
                self._register = 'ok'
                self._m.repl.echo("%s registration successful" % self.username)
            elif response.status == 401:
                self._register = 'unauthorized'
                self._m.repl.echo("%s registration failed (unauthorized)" % self.username)

        callid = self._m.do_request('REGISTER', self.registrar, {
            'cseq'       : self._cseq.next(),
            'local_ip'   : 'localhost',
            'local_port' : self.sips.portnum(),
            'local_user' : self.username,
            'remote_user': self.username,
        }, response)

        self._register = 'pending'

    def do_dial(self, *args):
        """Dial a peer
        Send an INVITE SIP command to the sip proxy.
        Peer is local (another account on the same epbxdclient instance).
        Usage: *from-account* dial *to-account*
        """
        self._m.repl.echo("%s: Dialing %s" % (self.username, args[0]))

        def response(callid, resp):
            if   resp.status == 404:
                self._m.repl.echo("Target %s not found" % args[0])
            elif resp.status == 100: # Trying
                pass
            elif resp.status == 180: # Ringing
                self._m.repl.echo("Remote called endpoint '%s' is ringing" % args[0])
            elif resp.status == 200: # OK
                self.transactions[resp.headers['call-id']] = resp
                self._m.repl.echo("%s: Call established" % self.username)

        callid = self._m.uuid()
        # open RTP and SRTP sockets
        rtps = SipServer(self.receive_rtp, mode='udp', data=callid)
        self._m.repl.echo("%s: Opening RTP socket %d/udp" % (self.username,	rtps.getsockname()[1]))

        callid = self._m.do_request('INVITE', self.proxy, {
            'call_id'    : callid,
            'cseq'       : self._cseq.next(),
            'local_ip'   : 'localhost',
            'local_port' : self.sips.portnum(),
            'local_user' : self.username,
            'remote_user': args[0],

            'media_port' : rtps.getsockname()[1],
        }, response)

        self.rtp_ports[callid] = [rtps, None]

    def do_ack(self, callid, *args):
        """Send ACK request.
        ACK message is send regarding an active transaction
        Usage: *account-name* ack *call-id*
        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False
        self._m.repl.echo("Sending ACK (transaction= %s)" % callid)

        t = self.transactions[callid].headers

        callid = self._m.do_request('ACK', self.proxy, {
            'local_ip'   : 'localhost',
            'local_port' : self.sips.portnum(),
            'local_user' : t['from'].user,
            'remote_user': t['to'].user,

            # transaction values
            'call_id'    : callid,
            'branch'     : t['via'].params['branch'],
            'to_tag'     : t['to'].params['tag'],
            'from_tag'   : t['from'].params['tag'],
            'cseq'       : t['cseq'].sequence,
        })

    def do_ringing(self, callid, *args):
        """Send a 180/RINGING response.

        Usage: *account-name* ringing *call-id*
        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        t = self.transactions[callid].headers
        t['resp_to_tag'] = self._m.uuid()

        self._m.do_request('ringing', self.proxy, {
            'local_ip'     : 'localhost',
            'local_port'   : self.sips.portnum(),
            'local_user'   : self.username,

            'last_Via:'    : "Via: "     + str(t['via']),
            'last_To:'     : "To: "      + str(t['to']),
            'last_From:'   : "From: "    + str(t['from']),
            'last_Call-ID:': "Call-ID: " + str(t['call-id']),
            'last_CSeq:'   : "CSeq: "    + str(t['cseq']),

            # transaction values
            'to_tag'       : t['resp_to_tag'], # generate To tag
        })

    def do_ok(self, callid, *args):
        """Send a 200/OK response

        Usage: *account-name* ok *call-id*
        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        # open RTP and SRTP sockets
        rtpsock = SipServer(self.rtp_receive, 'udp')
        self._m.repl.echo("%s: Listening for RTP datas on %s" % (self.username, rtpsock.getsockname()))
        self.rtpsocks[callid] = [rtpsock, None]

        t = self.transactions[callid].headers
        t['resp_to_tag'] = t.get('resp_to_tag', self._m.uuid())

        self._m.do_request('ok', self.proxy, {
            'local_ip'     : 'localhost',
            'local_port'   : self.sips.portnum(),
            'local_user'   : self.username,

            'last_Via:'    : "Via: "     + str(t['via']),
            'last_To:'     : "To: "      + str(t['to']),
            'last_From:'   : "From: "    + str(t['from']),
            'last_Call-ID:': "Call-ID: " + str(t['call-id']),
            'last_CSeq:'   : "CSeq: "    + str(t['cseq']),

            # transaction values
            'to_tag'       : t['resp_to_tag'],
            'media_port'   : rtpsock.getsockname()[1],
        })

    def do_play(self, callid, encoding, filename):
        """Play a sound file to a "connected" peer
        File is sent through a RTP channel

        Usage: *account-name* play *call-id* *encoding* *filename*
        NOTE : encoding is one of ulaw, alaw or gsm
        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        if encoding not in ENCODINGS:
            self._m.repl.echo("%s: unknown '%s' encoding" % (self.username, encoding))
            return False

        if not os.path.exists(filename):
            self._m.repl.echo("%s: file '%s' does not exists" % (self.username,	filename))
            return False

        t = self.transactions[callid]
        # connecting to peer RTP socket
        rtp_sock = SipSocket(host=t.payload.media_host, port=t.payload.media_port, mode='udp')

        pad1 = 2 << 6
        pad2 = ENCODINGS[encoding]

        # seq & tstamp are modified by nested method
        class Namespace: pass
        ns = Namespace()
        ns.seq  = random.randint(0, 32768)
        ns.tstamp = random.randint(0, 2**30)
        ssrc   = random.randint(0, 2**32)

        f = open(filename, 'rb')

        def send_rtp():
            rtp = f.read(160)
            if len(rtp) == 0:
                rtp_sock.close(); f.close(); return False

            rtp = pack('!ccHII', chr(pad1), chr(pad2), ns.seq, ns.tstamp, ssrc) + rtp
            rtp_sock.send(rtp)

            ns.seq += 1; ns.tstamp += 160
            return True

        self._m.repl.echo("%s: start sending RTP datas" % self.username);
        self._m.add_scheduled_action(.02, send_rtp)
        return True

    def do_rtpsave(self, callid, filename):
        """Save received RTP datas in a file
        NOTE: RTP datas received before this command are not saved

        Usage: *account-id* rtpsave *call-id* *filename*
        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        self.rtp_dump_files[callid] = file(filename, 'wb')

    ## Handle requests
    def req_invite(self, req):
        """INVITE request

            save transaction
        """
        self.transactions[req.headers['call-id']] = req

        return True

    def req_ack(self, req):
        """ACK request

            acknowledge a transaction
        """
        callid = req.headers['call-id']
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        t = self.transactions[callid].headers
        self._m.repl.echo("%s: Call established" % self.username)


