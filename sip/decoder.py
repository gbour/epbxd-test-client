#!/usr/bin/env python
# -*- coding: utf8 -*-

import re
from collections import namedtuple

Request  = namedtuple('Request', 'method uri headers content')
Response = namedtuple('Response', 'status reason headers content')

class Header(object):
    def __init__(self, raw, fields):
        self._raw = raw

        for k, v in fields.iteritems():
            setattr(self, k, v)

    def __str__(self):
        return self._raw

    def __repr__(self):
        return "H(%s)" % self._raw

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
            headers = dict([self.decode_header(k, v) for (k,v) in 
                [line.split(':', 1) for line in lines]])

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

    def decode_header(self, name, raw):
        name  = name.lower()
        value = raw.strip()

        try:
            value = getattr(self, "decode_header_"+name)(value)
        except AttributeError:
            pass
        except Exception, e:
            print e

        return (name, value)

    def decode_header_from(self, raw):
        """

            To: <sip:101@localhost:58129>;tag=as2aa26b43
            To: "101" <sip:101@localhost:58129>;tag=as2aa26b43
        """
        m =	re.match(
            "^\s*(?:\"(?P<displayname>[^\"]*)\"\s+)?<(?P<proto>[^:]+):(?P<user>[^:@]+)@(?P<host>[^:;]+)(?::(?P<port>\d+))?>(?P<params>.*)$",
            raw
        )
        if m is None:
            raise Exception

        value  = m.groupdict()
        value['params'] = dict(re.findall(";([^;=]+)(?:=([^;]*))", value['params']))

        return Header(raw, value)

    decode_header_to      = decode_header_from
    decode_header_contact = decode_header_from

    def decode_header_via(self, raw):
        """

            Via: SIP/2.0/UDP 10.0.0.11:5060;branch=z9hG4bK9252030874800754865-85861006;received=10.0.0.11
        """
        m = re.match("^SIP/2.0/(?P<proto>[^\s]+) (?P<host>[^:;]+):(?P<port>\d+)(?P<params>.*)$", raw)
        if m is None:
            raise Exception

        value  = m.groupdict()
        value['params'] = dict(re.findall(";([^;=]+)(?:=([^;]*))", value['params']))

        return Header(raw, value)

    def decode_header_cseq(self, raw):
        """

            CSeq: 1 INVITE
        """
        (seq, action) = raw.split(' ')
        return Header(raw, {'sequence': seq, 'action': action})



