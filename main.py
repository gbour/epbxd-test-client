#!/usr/bin/env python
# -*- coding: utf8 -*-

import asyncore
from   sip import Account, Manager, Repl

if __name__ == '__main__':
    m = Manager()
    m.repl = Repl(m.handle)

    #sip.REPL = sip.Repl()
    #sips = sip.SipServer(repl)
    for name in ('101','102'):
        acc = Account(name,'localhost',5060)
        #acc = Account(name,'localhost',7779)
        m.add_account(acc)

        m.repl.echo("Account %s listening on %d port" % (acc.username, acc.sips.portnum()))
    m.repl.flush()

    while True:
        try:
            # interrupt each 10 ms
            asyncore.loop(timeout=.01, count=1)
            m.scheduler()

        except KeyboardInterrupt:
            break

    print '\nend...'
    m.repl.cleanup()

