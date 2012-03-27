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
		m.add_account(acc)

		m.repl.echo("Account %s listening on %d port" % (acc.username, acc.sips.portnum()))
	m.repl.flush()

	try:
		asyncore.loop()
	except KeyboardInterrupt:
		pass

	print '\nend...'
	m.repl.cleanup()

