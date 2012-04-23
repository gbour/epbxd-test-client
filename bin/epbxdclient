#!/usr/bin/env python
# -*- coding: utf8 -*-

import yaml
import optparse
import asyncore
from   sip import Account, Manager, Repl

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config', dest='config_file', default='/etc/epbxdclient.cfg',
        metavar='CONFIG-FILE', help='Configuration file')

    (opts, args) = parser.parse_args()
    config = yaml.load(file(opts.config_file, 'rb').read())

    m = Manager()
    m.repl = Repl(m.handle)

    #sip.REPL = sip.Repl()
    #sips = sip.SipServer(repl)
    for name, params in config['accounts'].iteritems():
        (host, port) = params['registrar'].split(':')
        acc = Account(name, host, int(port))
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

