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

        # ANSI sequences
        """ ANSI sequences
        
            An ANSI sequence starts with ´ (0x27) character and is followed by several keys
            i.e: up arrow is e-s "´[A"
        """
        self.ansi_mode   = False
        self.ansi_buffer = ""
        self.sequences   = [
            "[A",	# up arrow
            "[B", # down arrow
            "[C", # right arrow
            "[D", # left arrow

            "[2~", # insert
            "[3~", # suppr
            "OH" , # home
            "OF" , # end
            "[5~" , # page up
            "[6~" , # page down
            "[1~", # home (keypad)
            "[4~", # end (keypad)
            "[E", # keypad middle key (5)
            "OP", # f1
            "OQ", # f2
            "OR", # f3
            "OS", # f4
            "[15~", # f5
            "[17~", # f6
            "[18~", # f7
            "[19~", # f8
            "[20~", # f9
            "[21~", # f10
            "[23~", # f11 ??
            "[24~", # f12
        ]


    def cleanup(self):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        self.logf.close()

    def handle_read(self):
        c = self.recv(1)

        if self.ansi_mode:
            self.ansi_buffer += c
            if self.ansi_buffer in self.sequences:
                self.ansi_mode = False

            return

        # start-of ANSI sequence
        if ord(c) == 27:
            self.ansi_mode = True; self.ansi_buffer = ""; return

        # carriage return
        elif c == '\n':
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
