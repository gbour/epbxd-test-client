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

import sys, os, asyncore, readline, tty, termios
from completion import Completion

# console ANSI colors
class Colors(object):
    END    = '\033[0m'
    BOLD   = '\033[1m'
    RED    = '\033[91m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'

    status = {
        1: BLUE,
        2: GREEN,
        3: YELLOW,
        4: RED
    }

INFO      = 1
OK        = 2
WARNING   = 3
ERROR     = 4


class Repl(asyncore.file_dispatcher):
    """read-eval-print loop object

        working asynchroneously
    """
    def __init__(self, callback):
        self.callback   = callback
        self.completion = Completion()

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

        # history
        self.histf = open('.history', 'a+')

        #NOTE: we only keep last 100 commands
        self.history = [line[:-1] for line in self.histf.readlines()]
        if len(self.history) > 100:
            self.histf.seek(0)
            self.history = self.history[-100:]
        self.curhist = None


    def cleanup(self):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        self.logf.close()
        self.histf.close()

    def handle_read(self):
        c = self.recv(1)

        if self.ansi_mode:
            self.ansi_buffer += c
            if self.ansi_buffer in self.sequences:

                if self.ansi_buffer == '[A' and len(self.history) > 0: # up arrow:
                    if self.curhist is None:
                        self.curhist = len(self.history)-1

                        if len(self.buffer) > 0:
                            self.history.append(''.join(self.buffer))
                    elif self.curhist > 0:
                        self.history[self.curhist] = ''.join(self.buffer)
                        self.curhist -= 1

                    if self.curhist >= 0:
                        # erase line (5 == prompt width)
                        sys.stdout.write('\r' + ' '*(5+len(''.join(self.buffer).expandtabs())) + '\r')
                        self.buffer = list(self.history[self.curhist])
                        self.prompt(''.join(self.buffer))

                elif self.ansi_buffer == '[B' and self.curhist is not None and\
                        self.curhist < len(self.history)-1:
                        sys.stdout.write('\r' + ' '*(5+len(''.join(self.buffer).expandtabs())) + '\r')

                        self.curhist += 1
                        self.buffer = list(self.history[self.curhist])
                        self.prompt(''.join(self.buffer))


                self.ansi_mode = False

            return

        # start-of ANSI sequence
        if ord(c) == 27:
            self.ansi_mode = True; self.ansi_buffer = ""; return

        # carriage return
        elif c == '\n':
            # do the job
            cmd = ''.join(self.buffer).strip()

            if len(cmd) > 0:
                self.curhist = None
                self.add_history(cmd)
                self.callback(cmd)

            # flush buffer
            del self.buffer[:]
            self.prompt(ret=True); return

        # backspace
        elif c == '\b' or ord(c) == 127:
            if len(self.buffer) > 0:
                l = len(self.buffer[-1].expandtabs())
                sys.stdout.write('\b'*l + ' '*l + '\b'*l)
                del self.buffer[-1]

            return

        #tabulation
        elif ord(c) == 9:
            status, cmd, values = self.completion.complete(''.join(self.buffer))
            if   status == 'invalid':
                print
                self.echo('command not found', status=ERROR)
            elif status == 'completion':
                print
                for val in values:
                    print "\t", val

                self.buffer = list(cmd)
                self.flush()
            return

        sys.stdout.write(c)
        self.buffer.append(c)

    def echo(self, data, flush=True, status=None):
        if status is not None:
            data = Colors.status[status] + data + Colors.END

        #1. save prompt (done in self.buffer)

        #2. write datas
        sys.stdout.write('\r' if flush else '')
        sys.stdout.write(data+'\n')

        #3. reset prompt
        #sys.stdout.write("[.]> ")
        if flush:
            self.flush()

    def flush(self, content=None, ret=False):
        if ret:
            sys.stdout.write('\n')
        sys.stdout.write("\r" +
            Colors.BOLD +
            "$> "       +
            Colors.END  +
            (content if content is not None else ''.join(self.buffer))
        )
    prompt=flush

    def debug(self, data):
        self.logf.write(data)
        self.echo(data)

    def add_history(self, command):
        self.history.append(command)
        self.histf.write(command+'\n')

    def writable(self):
        """
            NOTE: if writable() not set to False, file socket is NON-BLOCKING (using select())
        """
        return False
