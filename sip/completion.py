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


class Completion(object):
    def __init__(self):
        self.commands = set()

    def add_command(self, cmd):
        """Add a new command to completion
        """
        self.commands.add(cmd)

    def del_command(self, cmd):
        """Remove a command from completion

        NOTE: remove *all* commands starting with cmd
        """
        for c in list(self.commands):
            if c.startswith(cmd):
                self.commands.discard(c)
        
    def complete(self, cmd):
        """Try to complete a command
        
            2 possible returned values:
                replace command/list possibilities  : (completion, "new-command", ['choice 1','choice 2', ...])
                invalid command                     : (invalid   , msg          , None)

            i.e:
                guess('1')           -> (completion, '10', ['101','102'])
                guess('10')          -> (completion, '10', ['101','102'])
                guess('20')          -> (invalid, 'unknown 20* account', None)
                guess('101')         -> (completion, ['101 register','101 dial',...])
                guess('101 ring')    -> (completion, '101 ringing', [])
                guess('101 ringing') -> 
                    (completion, '101 ringing 0b489af3', [])                      if one transaction active only
                    (completion, '101 ringing 3f'      , ['3f54b655','3f40c34d']) if more than one transaction
                    (invalid   , "not found"           , [])                      if no transactions at all
        """
        def filter(g):
            # try to find the smallest common part
            try:
                pos =  g.index(' ', len(cmd))
                # if next char after cmd is a space, we search for next option arg
                if pos == len(cmd):
                    pos = g.index(' ', pos+1)
            except ValueError:
                return g

            return g[:pos]

        guessed = set([filter(g) for g in self.commands if g.startswith(cmd)])
        if   len(guessed) == 0:
            return ('invalid', "not found", [])
        elif len(guessed) == 1:
            return ('completion', guessed.pop(), [])
        
        # search if we can extend original cmd with common part
        def ljoin(l, r):
            for i in xrange(min(len(l), len(r))):
                if l[i] != r[i]:
                    return l[:i]
                
            return l

        # find smallest common part
        common = list(guessed)[0]
        for g in guessed:
            common = ljoin(common, g)

        return ('completion', common, sorted(guessed))

