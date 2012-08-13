# -*- coding: UTF8 -*-
import sys

__all__ = ['exit', 'printit', 'accounts']

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

        _automaton.register(self)


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

    """
    def do_quit(self):
        pass

    def do_dial(self):
        print 'dial',self
    """


def exit(msg):
    print msg
    sys.exit()

def printit(msg):
    print msg

def accounts():
    return [AccountProxy(name) for name in _automaton.accounts()]


_automaton = Automaton()
# Exporting action methods
#__all__  = [k[3:] for k in Automaton.__dict__.keys() if k.startswith('do_')]
#for action in __all__:
#    locals()[action] = getattr(_automaton, 'do_'+action)
