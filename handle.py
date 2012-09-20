# -*- coding: utf-8 -*-
import sys,os

sys.path.insert(0, os.path.dirname(__file__))

from mensa import scrape_mensa, meta_names

uri = "/index.xml"
if 'REQUEST_URI' in os.environ:
    uri = os.environ['REQUEST_URI']

mensa = None

if uri.endswith(".xml"):
    filename = os.path.basename(uri)
    mensa = filename[:-4]
    if not mensa in meta_names:
        mensa = None

if mensa:
    try:
        data = scrape_mensa(mensa)
        print "Content-Type: application/xml; charset=utf-8"
        print "Content-Length: "+str(len(data))
        print ""
        print data
    except Exception, e:
        print "Status: 404 Not Found"
        print "Content-Type: application/xml; charset=utf-8"
        print ""
        print """<?xml version="1.0" encoding="UTF-8"?>"""
        print "<error>"
        print " <code>404</code>"
        print " <message>Mensa not found</message>"
        print " <debug-data>" + repr(e) + "</debug-data>"
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
    for mensa in meta_names:
        print "  <list-item>" + mensa + ".xml</list-item>"
    print " </debug-data>"
    print "</error>"
