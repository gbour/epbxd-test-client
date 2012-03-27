#!/usr/bin/env python
# -*- coding: utf8 -*-

from collections import namedtuple

Request  = namedtuple('Request', 'method uri headers content')
Response = namedtuple('Response', 'status reason headers content')

class SipDecoder(object):
    def __init__(self):
        pass

    def decode(self, raw):
        messages = []

        eoh = start = 0
        while True:
            eoh = raw.find("\r\n\r\n", start)
            if eoh < 0:
                break

            lines   = raw[start:eoh].split("\r\n")
            som     = lines.pop(0)
            headers = dict([(k.lower(), v.strip()) for (k,v) in [line.split(':', 1) for line in lines]])

            length = int(headers.get('content-length', 0))
            start  = eoh+4+length

            messages.append(self.instanciate(som, headers, raw[eoh+4:start]))

        return messages

    def instanciate(self, som, headers, content):
        """decode Start-Of-Message header

            Instanciate Request() or Response() tuple
        """
        (p1,p2,p3) = som.split(' ', 2)
        if p1.startswith('SIP/'):
            # response
            return Response(int(p2), p3, headers, content)

        return Request(p1, p2, headers, content)
