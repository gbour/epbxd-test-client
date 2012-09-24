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
import repl

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

        self._registration = 'none'
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
        repl.info("Account %s: receiving incoming message on private socket" % self.username)
        self._m.receive(sock, data, extra)

    def receive_rtp(self, sock, data, callid):
        """Receive RTP data
        """
        repl.debug("%s: receiving RTP data (callid= %s)" % (self.username, callid))

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
        repl.debug("%s, csrcs=%s, payload=%d" % 
            (str(rtp), str(csrcs), (len(data)-12-4*rtp.cc)))

        if callid in self.rtp_dump_files:
            self.rtp_dump_files[callid].write(data[12+4*rtp.cc:])

    def do_status(self, *args):
        """Display account status
        """
        repl.info("%s account:\n . registration= %s" % (self.username, self._registration))

    def do_register(self, *args, **kwargs):
        """Register account at registrar.
        Send a REGISTER command to the registar, and handle the response.
        Usage: *account-name* register
        """
        repl.info("Registering %s" % self.username)

        def response(callid, response):
            if   response.status == 200:
                self._registration = 'ok'
                repl.ok("%s registration successful" % self.username)
            elif response.status == 401:
                self._registration = 'unauthorized'
                repl.error("%s registration failed (unauthorized)" % self.username)
            elif response.status == 404:
                self._registration = 'not found'
                repl.error("%s registration failed (not found)" % self.username)

            if 'callback' in kwargs:
                kwargs['callback'](self, callid, response)

        callid = self._m.do_request('REGISTER', self.registrar, {
            'cseq'       : self._cseq.next(),
            'local_ip'   : 'localhost',
            'local_port' : self.sips.portnum(),
            'local_user' : self.username,
            'remote_user': self.username,
        }, response)

        self._registration = 'pending'
        return callid

    def do_dial(self, *args):
        """Dial a peer
        Send an INVITE SIP command to the sip proxy.
        Peer is local (another account on the same epbxdclient instance).
        Usage: *from-account* dial *to-account*
        """
        repl.info("%s: Dialing %s" % (self.username, args[0]))

        def response(callid, resp):
            if   resp.status == 404:
                repl.error("Target %s not found" % args[0])
            elif resp.status == 100: # Trying
                pass
            elif resp.status == 180: # Ringing
                repl.warning("%s : Remote called endpoint '%s' is ringing" % (self.username, args[0]))
            elif resp.status == 200: # OK
                self.transactions[resp.headers['call-id']] = resp
                repl.ok("%s: Call established" % self.username)
            elif resp.status == 503: # Unavailable
                repl.error("%s: Service '%s' is unavailable" % (self.username, args[0]))

        callid = self._m.uuid()
        # open RTP and SRTP sockets
        rtps = SipServer(self.receive_rtp, mode='udp', data=callid)
        repl.debug("%s: Opening RTP socket %d/udp" % (self.username,	rtps.getsockname()[1]))
        #self._m.add_to_completion("%s hangup %s" % (self.username, callid))
        self._m.add_to_completion("%s bye %s" % (self.username, callid))
        self._m.add_to_completion("%s cancel %s" % (self.username, callid))
        self._m.add_to_completion("%s ack %s" % (self.username, callid))

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
        return True

    def do_ack(self, callid, *args):
        """Send ACK request.
        ACK message is send regarding an active transaction
        Usage: *account-name* ack *call-id*
        """
        if callid not in self.transactions:
            repl.error("Transaction %s not found!" % callid); return False
        repl.info("%s : Sending ACK (transaction= %s)" % (self.username, callid))

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
            repl.warning("Transaction %s not found!" % callid); return False

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

        return True

    def do_ok(self, callid, *args):
        """Send a 200/OK response

        Usage: *account-name* ok *call-id*
        NOTE: the OK response is contextual (may respond to INVITE or BYE requests)
        """
        if callid not in self.transactions:
            repl.error("Transaction %s not found!" % callid); return False

        t = self.transactions[callid].headers
        headers = {
            'local_ip'     : 'localhost',
            'local_port'   : self.sips.portnum(),
            'local_user'   : self.username,

            'last_Via:'    : "Via: "     + str(t['via']),
            'last_To:'     : "To: "      + str(t['to']),
            'last_From:'   : "From: "    + str(t['from']),
            'last_Call-ID:': "Call-ID: " + str(t['call-id']),
            'last_CSeq:'   : "CSeq: "    + str(t['cseq']),
        }

        meth = self.transactions[callid].method
        if   meth == 'INVITE':
            repl.info("%s: Establishing call with %s" % (self.username, getattr(t['from'], 'displayname', 'anonymous')))

            # open RTP and SRTP sockets
            rtpsock = SipServer(self.receive_rtp, 'udp')
            repl.debug("%s: Listening for RTP datas on %s" % (self.username, rtpsock.getsockname()))
            self.rtp_ports[callid] = [rtpsock, None]
            headers['media_port'] = rtpsock.getsockname()[1]

        elif meth == 'BYE':
            repl.info("%s : Hanging up call with %s" % (self.username, getattr(t['from'], 'displayname', 'anonymous')))

            # deleting transaction, closing RTP socket
            repl.debug("%s: Closing RTP socket" % self.username)
            del self.rtp_ports[callid]
            del self.transactions[callid]


        headers['resp_to_tag'] = t['resp_to_tag'] = t.get('resp_to_tag', self._m.uuid())

        self._m.do_request('ok', self.proxy, headers)

    def do_bye(self, callid, *args):
        """Send a BYE request.
        Hangup an active channel

        Usage: *account-name* bye *call-id*
        """
        if callid not in self.transactions:
            repl.error("Transaction %s not found!" % callid); return False
        repl.info("%s : Sending BYE (transaction= %s), closing RTP socket" % (self.username, callid))

        t = self.transactions[callid].headers

        self._m.do_request('BYE', self.proxy, {
            'local_ip'     : 'localhost',
            'local_port'   : self.sips.portnum(),
            'local_user'   : self.username,
            'remote_user': t['to'].user,

            # transaction values
            'call_id'    : callid,
            'branch'     : t['via'].params['branch'],
            'to_tag'     : t['to'].params['tag'],
            'from_tag'   : t['from'].params['tag'],
            'cseq'       : t['cseq'].sequence,
        })

        #closing RTP socket (we don't wait BYE response)
        del self.rtp_ports[callid]

    def do_play(self, callid, encoding, filename):
        """Play a sound file to a "connected" peer
        File is sent through a RTP channel

        Usage: *account-name* play *call-id* *encoding* *filename*
        NOTE : encoding is one of ulaw, alaw or gsm
        """
        if callid not in self.transactions:
            repl.error("Transaction %s not found!" % callid); return False

        if encoding not in ENCODINGS:
            repl.error("%s: unknown '%s' encoding" % (self.username, encoding))
            return False

        if not os.path.exists(filename):
            repl.error("%s: file '%s' does not exists" % (self.username, filename))
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

        repl.debug("%s: start sending RTP datas" % self.username);
        self._m.add_scheduled_action(.02, send_rtp)
        return True

    def do_rtpsave(self, callid, filename):
        """Save received RTP datas in a file
        NOTE: RTP datas received before this command are not saved

        Usage: *account-id* rtpsave *call-id* *filename*
        """
        if callid not in self.transactions:
            repl.error("Transaction %s not found!" % callid); return False

        self.rtp_dump_files[callid] = file(filename, 'wb')

    ## Handle requests
    def req_invite(self, req):
        """INVITE request

            save transaction
        """
        repl.warning("%s : Is invited by %s" % (self.username, getattr(req.headers['from'], 'displayname', 'anonymous')))
        self.transactions[req.headers['call-id']] = req

        return True

    def req_ack(self, req):
        """ACK request

            acknowledge a transaction
        """
        callid = req.headers['call-id']
        if callid not in self.transactions:
            repl.error("Transaction %s not found!" % callid); return False

        t = self.transactions[callid].headers
        repl.warning("%s: Call established" % self.username)

    def req_bye(self, req):
        """receive BYE request

            Save transaction
        """
        self.transactions[req.headers['call-id']] = req

        repl.warning("%s: Asked to hangup call" % self.username)
        return True

    def req_ok(self, req):
        t = self.transactions[req.headers['call-id']]
        if t.method == 'BYE':
            del self.transactions[req.headers['call-id']]

        return True
