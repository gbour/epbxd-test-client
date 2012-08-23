# -*- coding: UTF8 -*-
import sys
import threading

__all__ = ['exit', 'printit', 'accounts', 'sync']

"""
class OnResponse(object):
    def __init__(self, originator, code):
        self.originator = originator
        self.code       = code

    def onsuccess(self, callback):
        if 'success' in self.code:
            callback()

        return False

    def onerror(self, callback):
        if 'error'in self.code:
            callback()

        return False
"""

class Action(object):
    def __init__(self, originator, action, timeout, callbacks):
        self.originator = originator
        self.action     = action
        self.timeout    = timeout
        self.callbacks  = callbacks

        self.lock       = threading.Lock()
        self.lock.acquire()

        _automaton.register(self)

    def serialize(self):
        """
            NOTE: we cannot serialize callbacks 
        """
        import pickle
        return pickle.dumps({
            'id'        : id(self),
            'originator': self.originator.name,
            'action'    : self.action,
            'timeout'   : self.timeout,
        }, -1)

    def trigger(self, event, *args, **kwargs):
        if event in self.callbacks:
            self.callbacks[event](self, *args, **kwargs)

    def unlock(self, status):
        self.status = status
        self.lock.release()

class AccountProxy(object):
    def __init__(self, name):
        self.name = name

    def register(self, timeout=-1, on_ok=None, on_error=None, on_timeout=None):
        return Action(self, 'register', timeout, {
            'ok'     : on_ok,
            'error'  : on_error,
            'timeout': on_timeout
        })

    def __str__(self):
        return self.name

        

class Automaton(object):
    def __init__(self):
        self.actions = list()

    def set_ctrl(self, ctrl):
        self.ctrl = ctrl

    def register(self, action):
        self.actions.append(action)
        self.ctrl.doaction(action)

    def accounts(self):
        return self.ctrl.mngr.accounts.keys()

    def printit(self, msg):
        self.repl.automaton("[automaton] " + msg)

    """
    def do_quit(self):
        pass

    def do_dial(self):
        print 'dial',self
    """


def exit(msg=None):
    if msg is not None:
        printit(msg)
    #TODO: at now, only exit sub-process. Must initiate program end sequence
    sys.exit()

def printit(msg):
    _automaton.printit(msg)

def accounts():
    return [AccountProxy(name) for name in _automaton.accounts()]

class sync():
    def __init__(self, *states):
        self.states = states

    def __enter__(self):
        print "sync:entering"
        status = False
        for state in self.states:
            # lock until state updated
            state.lock.acquire()
            print "sync:unlocked:", state.originator
            status = status and state.status

        return status

    def __exit__(self, type, value, traceback):
        pass

_automaton = Automaton()
# Exporting action methods
#__all__  = [k[3:] for k in Automaton.__dict__.keys() if k.startswith('do_')]
#for action in __all__:
#    locals()[action] = getattr(_automaton, 'do_'+action)
