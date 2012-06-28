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

import re
from collections import namedtuple

Request  = namedtuple('Request', 'method uri headers payload')
Response = namedtuple('Response', 'status reason headers payload')


class SDP(object):
    def __init__(self):
        self.media_host = "::"
        self.media_port = 0

    def parse(self, raw):
        for k, v in [i.split('=') for i in raw.split('\r\n')[:-2]]:
            if not hasattr(self, '_decode_'+k):
                continue

            getattr(self, '_decode_'+k)(v)

    def _decode_c(self, raw):
        """

            c=IN IP4 192.168.10.22
        """
        (family, version, self.media_host) = raw.split(' ')

    def _decode_m(self, raw):
        """

            m=audio 48521 RTP/AVP 8 0
        """
        (media, port, transport, fmts) = raw.split(' ', 3)

        self.media_port = int(port)

    def __str__(self):
        return "SDP(%s:%d)" % (self.media_host, self.media_port)

    def __repr__(self):
        return str(self)


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
            headers = dict([self.decode_header(h) for h in lines])

            length = int(headers.get('content-length', 0))
            start  = eoh+4+length

            messages.append(self.instanciate(som, headers, raw[eoh+4:start]))

        return messages

    def instanciate(self, som, headers, content):
        """decode Start-Of-Message header

            Instanciate Request() or Response() tuple
        """
        (p1,p2,p3) = som.split(' ', 2)

        payload = SDP()
        payload.parse(content)
        if p1.startswith('SIP/'):
            # response
            return Response(int(p2), p3, headers, payload)

        return Request(p1, p2, headers, payload)

    def decode_header(self, header):
        name, value = header.split(':',1)
        name        = name.lower()
        value       = value.strip()

        try:
            value = getattr(self, "decode_header_"+name)(value)
        except AttributeError:
            pass
        except Exception, e:
            #print "Exception=", e, name
            pass

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



