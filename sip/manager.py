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

import os, re, uuid, time
from sip import repl
from sip.sipsocket import SipSocket
from sip.decoder   import *
from sip import repl

class Manager(object):
    def __init__(self, patterns_dir):
        self.accounts = {}
        self.sockets  = {}
        self.patterns = {}

        # transactions contains (action, state, account) tuples
        self.transactions = {}

        # servers connections
        self.connections  = {}

        for filename in os.listdir(patterns_dir):
            with open(os.path.join(patterns_dir, filename), 'r') as f:
                self.patterns[filename.lower()] = f.read()

        self.decoder = SipDecoder()

        # scheduled actions
        self._scheduler = []

        self.completion = ManagerCompletion(self, repl._default.completion)

    def add_to_completion(self, cmd):
        self.completion.add_command(cmd)

    def add_account(self, accnt):
        self.accounts[accnt.username] = accnt
        accnt.set_manager(self)

        self.completion.add_account(accnt)

    def help(self, args):
        from sip.account import Account
        def print_help(cmd, fun, long=False):
            txt = list()
            txt.append("\n %-10s" % cmd)
            if fun.__doc__ is not None:
                doc = fun.__doc__.strip().split('\n')
                txt.append("- %s" % doc[0])

                if long:
                    txt.append('\n')
                    for line in doc[1:]:
                        txt.append(' '*4+line.strip())

            return ''.join(txt)

        if len(args) > 0:
            if not hasattr(Account, 'do_'+args[0]):
                repl.error("Unknown *%s* command!" % args[0], place=repl.INBETWEEN); return False

            fun = getattr(Account, 'do_'+args[0])
            repl.info(print_help(args[0], fun, long=True), place=repl.AFTER)
            return True

        # list all available commands
        helps = list()
        for name, fun in sorted([(name, obj) for (name, obj) in Account.__dict__.iteritems() \
                                if name.startswith('do_')]):
            helps.append(print_help(name[3:], fun))

        repl.info(''.join(helps), place=repl.AFTER)

        return True

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
        if parts[0] == 'help':
            return self.help(parts[1:])

        accnt = self.accounts.get(parts[0], None)
        if accnt is None:
            repl.error("Unknown *%s* account" % parts[0], place=repl.INBETWEEN); return False
        if len(parts) < 2:
            repl.error("No action specified", place=repl.INBETWEEN); return False

        action = parts[1].lower()
        if not hasattr(accnt, 'do_'+action):
            repl.error("Unknown '%s' action" % action, place=repl.INBETWEEN); return False

        repl.debug("", place=repl.INBETWEEN)
        try:
            return getattr(accnt, 'do_'+action)(*parts[2:])
        except TypeError:
            repl.error("Invalid number of arguments for '%s' action" % action, place=repl.INBETWEEN)
            return False


    def do_request(self, action, server, mapping, callback=None):
        """Send request to SIP server
        """
        msg = self.patterns.get(action.lower(), None)
        if msg is None:
            return False

        mapping.update({
            'remote_ip'    : server.host,
            'remote_port'  : server.port,
            #TODO: should we use server.transport ?
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

        conn = self.get_connection(server)
        print 'CONN=',conn
        try:
            repl.debug("%s -> %s\n" % (conn.getsockname(), conn.getpeername()))
        except:
            # fail when using UDP transport
            pass
        repl.debug(msg[:-2] if msg.endswith('\r\n\r\n') else msg)
    
        ret  = conn.send(msg)
        return mapping['call_id']

    def uuid(self):
        return str(uuid.uuid4())

    def get_connection(self, server):
        conn = self.connections.get("%s://%s:%d" % (server.transport, server.host, server.port), None)
        if conn is None:
            conn = SipSocket(sock=None, host=server.host, port=server.port,
                             callback=self.receive, mode=server.transport)
            self.connections["%s://%s:%d" % (server.transport, server.host, server.port)] = conn

        return conn

    def receive(self, sock, raw, extra):
        try:
            repl.debug("%s -> %s\n" % (sock.getpeername(), sock.getsockname()))
        except:
            # fail when using UDP transport
            pass
        repl.debug(raw[:-2] if raw.endswith('\r\n\r\n') else raw)
        for msg in self.decoder.decode(raw):
            repl.debug(str(msg)+'\n')
            getattr(self, 'handle_'+msg.__class__.__name__.lower())(msg)

    def handle_response(self, resp):
        callid = resp.headers['call-id']

        trans  = self.transactions.get(callid, None)
        if trans is None:
            repl.warning("transaction '%s' not found. Response ignored" % trans); return False

        if trans[-1] is not None:
            return trans[-1](callid, resp)
        return False


    def handle_request(self, req):
        """
            A request is incoming on a socket used to send data to the server (generic socket).
            Must be redispatch to correct account (based on To header user)
        """
        username = req.headers['to'].user
        if username not in self.accounts:
            repl.error("Unknown targeted '%s' account" % username); return False

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


class ManagerCompletion(object):
    def __init__(self, mngr, completion):
        self.mngr       = mngr
        self.completion = completion

        self.set_help()

    def set_help(self):
        # help
        from sip.account import Account
        for name, fun in sorted([(name, obj) for (name, obj) in Account.__dict__.iteritems() \
                                if name.startswith('do_')]):
            self.completion.add_command('help '+name[3:])

    def add_command(self, cmd):
        self.completion.add_command(cmd)

    def add_account(self, accnt):
        self.completion.add_command("%s register" % accnt.username)

        for name in self.mngr.accounts.iterkeys():
            if name == accnt.username:
                continue

            self.completion.add_command("%s dial %s" % (name, accnt.username))
            self.completion.add_command("%s dial %s" % (accnt.username, name))

