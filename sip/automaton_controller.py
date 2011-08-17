#!/usr/bin/env python
# -*- coding: UTF8 -*-

import time
import threading
from multiprocessing import Process, Queue

from sip import repl, automaton

class AutomatonController(object):
    def __init__(self, mngr):
        self.ctrl = None
        self.mngr = mngr
        self.orders    = Queue()
        self.responses = Queue()
        self.pendings  = dict()

    def launch(self, script):
        #TODO: checks (file exists, is readable, ...)

        self.ctrl = Process(name='automaton', target=self._controller, args=(script,))
        self.ctrl.start()

    def eventloop(self):
        """eventloop() is executed in main process.

            1) it execute orders from script
            2) it destroy dead script process
        """
        while not self.orders.empty():
            import pickle
            order = pickle.loads(self.orders.get())

            accnt = self.mngr.accounts[order['originator']]
            callid = getattr(accnt,'do_'+order['action'])(callback=self.handle_response)
            self.pendings[callid] = order

        if self.ctrl is not None and not self.ctrl.is_alive():
            self.ctrl.terminate()
            self.ctrl = None

    def handle_response(self, account, callid, response):
        order = self.pendings.get(callid,None)
        self.responses.put((order,callid,response))

    def _controller(self, scriptname):
        repl.automaton('[automaton] controller process launched')
        self.threads  = dict()
        # actions triggered by the script, waiting for response
        self.actions  = dict()
        self.timers   = list()

        self.timerLocks = dict()
        self.eventLocks = dict()
    
        automaton._automaton.set_ctrl(self)
        automaton._automaton.repl = repl

        self.xlocals = dict([(name, getattr(automaton, name)) for name in automaton.__all__])

        t = threading.Thread(target=execfile, args=(scriptname, {}, self.xlocals))
        self.threads['main'] = t

        t.start()
        repl.automaton("[automaton] executing '%s' script" % scriptname)
        while True:
            time.sleep(.1)
            # handle timeouts
            ref = time.time()
            for (clock, actionid) in self.timers:
                if clock <= ref:
                    act = self.actions[actionid].callbacks['timeout']

                    # xlocals is enriched with variables declared in script previously executed
                    xglobals = dict(self.xlocals)
                    xglobals['__builtins__'] = globals()['__builtins__']
                    #http://stackoverflow.com/questions/4558104/python-evalcompile-sandbox-globals-go-in-sandbox-unless-in-def-why
                    callback = type(act)(
                        act.func_code, xglobals,
                        act.func_name, act.func_defaults, act.func_closure
                    )

                    t = threading.Thread(target=callback, args=(self.actions[actionid].originator,))
                    self.threads['loop'] = t
                    t.start()

                    #TODO: notify main controller to stop monitoring this action
                    # for an answer
                    self.timers.remove((clock,actionid))

            # handle responses
            while not self.responses.empty():
                (order, callid, response) = self.responses.get()
                action = self.actions[order['id']]

                act = None
                if response.status >= 200 and response.status < 300:
                    act = action.callbacks['ok']
                elif response.status >= 400:
                    act = action.callbacks['error']

                if act is not None:
                    xglobals = dict(self.xlocals)
                    xglobals['__builtins__'] = globals()['__builtins__']
                    callback = type(act)(
                        act.func_code, xglobals,
                        act.func_name, act.func_defaults, act.func_closure
                    )

                    t = threading.Thread(target=callback, args=(action.originator, response))
                    self.threads['loop'] = t
                    t.start()

                    # we must remove timeout if exists
                    for (clock, actionid) in list(self.timers):
                        if actionid == order['id']:
                            self.timers.remove((clock, actionid))

            # cleanup dead threads
            for name in list(self.threads.keys()):
                if not self.threads[name].is_alive():
                    del self.threads[name]


            if len(self.threads) == 0 and len(self.pendings) == 0 and len(self.timers) == 0:
                repl.automaton("[automaton] script '%s' ended" % scriptname); break

    def doaction(self, action):
        """ new action triggered from script 
        
            NOTE: automaton runs in a different process than program event loop
        """
        # send order to main process
        self.actions[id(action)] = action
        self.orders.put(action.serialize())
        if action.timeout > 0:
            self.timers.append((time.time()+action.timeout, id(action)))

