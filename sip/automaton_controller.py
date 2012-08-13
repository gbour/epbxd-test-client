#!/usr/bin/env python
# -*- coding: UTF8 -*-

import time
import threading
from multiprocessing import Process

from sip import repl, automaton

class AutomatonController(object):
    def __init__(self, mngr):
        self.ctrl = None
        self.mngr = mngr

    def launch(self, script):
        #TODO: checks (file exists, is readable, ...)

        self.ctrl = Process(name='automaton', target=self._controller, args=(script,))
        self.ctrl.start()

    def cleanup(self):
        if self.ctrl is not None and not self.ctrl.is_alive():
            self.ctrl.terminate()
            self.ctrl = None

    def _controller(self, scriptname):
        repl.info('[automaton] controller process launched')
        self.threads  = dict()
        self.pendings = dict()
        self.timers   = list()

        self.timerLocks = dict()
        self.eventLocks = dict()
    
        automaton._automaton.set_ctrl(self)

        xlocals = dict([(name, getattr(automaton, name)) for name in automaton.__all__])
        print xlocals
        t = threading.Thread(target=execfile, args=(scriptname, {}, xlocals))
        self.threads['main'] = t

        t.start()
        repl.info("[automaton] executing '%s' script" % scriptname)
        while True:
            time.sleep(.1)
            for name in list(self.threads.keys()):
                if not self.threads[name].is_alive():
                    del self.threads[name]

            # check timers
            ref = time.time()
            for (clock, clb, args) in self.timers:
                if clock <= ref:
                    clb(*args)
                    self.timers.remove((clock,clb,args))

            if len(self.threads) == 0 and len(self.pendings) == 0 and len(self.timers) == 0:
                repl.info("[automaton] script execution ended"); break

    def doaction(self, action):
        """ new action triggered from script """

        def onresponse(accnt, callid, response):
            repl.info("%s: response %d" % (callid, response.status))
        def ontimeout(callid):
            repl.info("%s: timeout" % callid)

            if 'timeout' in action.callbacks and action.callbacks['timeout'] is not None:
                action.callbacks['timeout'](callid)

        account = self.mngr.accounts[action.originator.name]
        callid = getattr(account, 'do_'+action.action)(callback=onresponse)
        self.pendings[callid] = action
        if action.timeout > 0:
            self.timers.append((time.time()+action.timeout, ontimeout, (callid,)))
        
        repl.info("[automaton] pending action %s (with %d timeout)" % (callid, action.timeout))
