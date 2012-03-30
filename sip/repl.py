#!/usr/bin/env python
# -*- coding: utf8 -*-

import sys, os, asyncore, readline, tty, termios

class Repl(asyncore.file_dispatcher):
    """read-eval-print loop object

        working asynchroneously
    """
    def __init__(self, callback):
        self.callback = callback

        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
    
        # bufferless stdout
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

        self.buffer = []
        asyncore.file_dispatcher.__init__(self, sys.stdin)

        #TODO: erase or append option
        self.logf = open('./trace.log', 'w')

    def cleanup(self):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        self.logf.close()

    def handle_read(self):
        c = self.recv(1)

        # carriage return
        if c == '\n':
            # do the job
            self.callback(''.join(self.buffer))

            # flush buffer
            del self.buffer[:]
            self.prompt(); return

        # backspace
        elif c == '\b' or ord(c) == 127:
            if len(self.buffer) > 0:
                l = len(self.buffer[-1].expandtabs())
                sys.stdout.write('\b'*l + ' '*l + '\b'*l)
                del self.buffer[-1]

            return

        sys.stdout.write(c)
        self.buffer.append(c)

    def echo(self, data, flush=False):
        sys.stdout.write('\n'+data)

        if flush:
            self.flush()

    def flush(self):
            self.prompt(''.join(self.buffer))

    def prompt(self, content=''):
        sys.stdout.write("\n[.]> "+content)


    def debug(self, data):
        self.logf.write(data)
        self.echo(data)
