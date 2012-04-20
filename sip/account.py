#!/usr/bin/env python
# -*- coding: utf8 -*-

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


class Account(object):
    def __init__(self, username, domain, port=5060):
        self.username = username
        self.domain   = domain
        self.port     = port

        # open client port
        self.sips     = SipServer(self.receive)

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

    def receive(self, sock, data, extra):
        """Receive data from private socket
        """
        self._m.repl.echo("Account %s: receiving incoming message on private socket" % self.username)
        self._m.receive(sock, data)

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
        rtps = SipServer(self.receive_rtp, mode='udp', data=callid)
        self._m.repl.echo("%s: Opening RTP socket %d/udp" % (self.username,	rtps.getsockname()[1]))

        callid = self._m.do_request('INVITE', (self.domain, self.port), {
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
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False
        self._m.repl.echo("Sending ACK (transaction= %s)" % callid)

        t = self.transactions[callid].headers

        callid = self._m.do_request('ACK', (self.domain, self.port), {
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
        """Send a Ringing response

        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        t = self.transactions[callid].headers
        t['resp_to_tag'] = self._m.uuid()

        self._m.do_request('ringing', (self.domain, self.port), {
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
        """Send a OK response
        """
        if callid not in self.transactions:
            self._m.repl.echo("Transaction %s not found!" % callid); return False

        t = self.transactions[callid].headers
        t['resp_to_tag'] = t.get('resp_to_tag', self._m.uuid())

        self._m.do_request('ok', (self.domain, self.port), {
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
        })

    def do_play(self, callid, encoding, filename):
        """

            NOTE: we presume file is in PCM A-LAW format
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


