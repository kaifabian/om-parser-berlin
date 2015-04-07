# -*- coding: utf-8 -*-
import sys
import os

import traceback

import IPy


sys.path.insert(0, os.path.dirname(__file__))
from mensa import scrapeMensaByName, metaNames


DEBUG_NETS = [
    "10.0.0.0/8",
    "127.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/24",
]


DEBUG_IPS = IPy.IPSet(map(IPy.IP, DEBUG_NETS))
REQUEST_IP = IPy.IP(os.environ.get('REMOTE_ADDR', '0.0.0.0'))

uri = os.environ.get('REQUEST_URI', '/')

mensa = None

if uri.endswith(".xml"):
    filename = os.path.basename(uri)
    mensa = filename[:-4]
    if not mensa in metaNames:
        mensa = None

if mensa:
    try:
        data = scrapeMensaByName(mensa)
        print "Content-Type: application/xml; charset=utf-8"
        print "Content-Length: "+str(len(data))
        print ""
        print data
    except Exception, e:
        print "Status: 404 Not Found"
        if REQUEST_IP not in DEBUG_IPS:
            print ""
        else:
                print "Content-Type: application/xml; charset=utf-8"
                print ""
                print """<?xml version="1.0" encoding="UTF-8"?>"""
                print "<error>"
                print " <code>404</code>"
                print " <message>Mensa not found</message>"
                print " <debug-data><![CDATA["
                print traceback.format_exc()
                print " ]]></debug-data>"
                print "</error>"

else:
    print "Status: 404 Not Found"
    print "Content-Type: application/xml; charset=utf-8"
    print ""
    print """<?xml version="1.0" encoding="UTF-8"?>"""
    print "<error>"
    print " <code>404</code>"
    print " <message>Mensa not found</message>"
    print " <debug-data>"
    print "  <list-desc>Valid filenames</list-desc>"
    for mensa in metaNames:
        print "  <list-item>" + mensa + ".xml</list-item>"
    print " </debug-data>"
    print "</error>"
