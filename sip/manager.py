#!/usr/bin/env python
# -*- coding: utf8 -*-

import os, re, uuid, time
from sip import repl
from sip.sipsocket import SipSocket
from sip.decoder   import *

class Manager(object):
    def __init__(self):
        self.accounts = {}
        self.sockets  = {}
        self.raw_messages = {}

        # transactions contains (action, state, account) tuples
        self.transactions = {}

        # servers connections
        self.connections  = {}

        for filename in os.listdir('./res'):
            with open(os.path.join('./res', filename), 'r') as f:
                self.raw_messages[filename.lower()] = f.read()

        self.decoder = SipDecoder()

        # scheduled actions
        self._scheduler = []

    def add_account(self, accnt):
        self.accounts[accnt.username] = accnt
        accnt.set_manager(self)

    def handle(self, cmd):
        """Handle command from CLI

            i.e:
                101 register
                101	dial 102
                101 ack 458d54ef452a
        """

        #NOTE: filter remove multi-spaces
        cmd = cmd.strip()
        if len(cmd) == 0:
            return True

        parts = filter(lambda x: len(x) > 0, cmd.split(' '))
        accnt = self.accounts.get(parts[0], None)

        if accnt is None:
            self.repl.echo("Unknown '%s' account" % parts[0]); return False
        if len(parts) < 2:
            self.repl.echo("No action specified"); return False

        action = parts[1].lower()
        if not hasattr(accnt, 'do_'+action):
            self.repl.echo("Unknown '%s' action" % action); return False

        return getattr(accnt, 'do_'+action)(*parts[2:])


    def do_request(self, action, (domain, port), mapping, callback=None):
        """Send request to SIP server
        """
        msg = self.raw_messages.get(action.lower(), None)
        if msg is None:
            return False

        mapping.update({
            'remote_ip'    : domain,
            'remote_port'  : port,
            'transport'    : 'TCP',
            'branch'       : mapping.get('branch'  , self.uuid()),
            'from_tag'     : mapping.get('from_tag', self.uuid()),
            'to_tag'       : mapping.get('to_tag'  , self.uuid()),
            'call_id'      : mapping.get('call_id' , self.uuid()),
            'local_ip_type': 4,
            'media_ip_type': 4,
            'media_ip'     : mapping['local_ip'],
            'media_port'   : mapping.get('media_port', 0),
            'ua'           : 'epbxd-pytest 0.1',
        })

        self.transactions[mapping['call_id']] = [action, None, callback]

        def domap(m):
            if m.group(1) == 'len':
                return '[len]'

            return str(mapping.get(m.group(1), "NONE"))
        msg = re.sub("\[([^\]]+)\]", domap, msg)

        # compute payload length
        # payload length is only known after variables substitutions
        try:
            length = len(msg) - msg.index('\r\n\r\n') - 4
        except ValueError:
            length = 0

        msg = msg.replace('[len]', str(length))

        conn = self.get_connection(domain, port)
        self.repl.debug("%s -> %s\n" % (conn.getsockname(), conn.getpeername()))
        self.repl.debug(msg)
    
        ret  = conn.send(msg)
        return mapping['call_id']

    def uuid(self):
        return str(uuid.uuid4())

    def get_connection(self, host, port):
        conn = self.connections.get("%s:%d" % (host, port), None)
        if conn is None:
            conn = SipSocket(sock=None, host=host, port=port, callback=self.receive)
            self.connections["%s:%d" % (host, port)] = conn

        return conn

    def receive(self, sock, raw, extra):
        self.repl.debug("%s -> %s\n" % (sock.getpeername(), sock.getsockname()))
        self.repl.debug(raw)
        for msg in self.decoder.decode(raw):
            self.repl.echo(str(msg))
            getattr(self, 'handle_'+msg.__class__.__name__.lower())(msg)

    def handle_response(self, resp):
        callid = resp.headers['call-id']

        trans  = self.transactions.get(callid, None)
        if trans is None:
            self.repl.echo("transaction '%s' not found. Response ignored" % trans); return

        if trans[-1] is not None:
            trans[-1](callid, resp)


    def handle_request(self, req):
        """
            A request is incoming on a socket used to send data to the server (generic socket).
            Must be redispatch to correct account (based on To header user)
        """
        username = req.headers['to'].user
        if username not in self.accounts:
            self.repl.echo("Unknown targeted '%s' account" % username); return False

        return getattr(self.accounts[username], 'req_'+req.method.lower())(req)


    def add_scheduled_action(self, step, callback):
        self._scheduler.append([time.time(), step, callback])

    def scheduler(self):
        now = time.time()

        deletes = []
        for action in self._scheduler:
            if action[0] > now:
                continue

            if action[2]():
                action[0] += action[1]
            else:
                deletes.append(action)

        for x in deletes:
            self._scheduler.remove(x)
