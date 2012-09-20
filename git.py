# -*- coding: utf-8 -*-
import sys,os
import traceback
import tempfile
import hashlib
from subprocess import *

sys.path.insert(0, os.path.dirname(__file__))

def serve_error():
    print "Status: 500 Internal Server Error"
    print "Content-Type: text/plain; charset=utf-8"
    print "Content-Disposition: inline"
    print ""
    print "Something went wrong:"
    traceback.print_exc()
    sys.exit(0)

try:
    location = os.path.dirname(os.path.realpath(__file__))
    if not os.path.isdir(os.path.join(location, ".git")):
        raise Exception("Called in non-git folder")
    
    request_filename = "-x-github-pull-queue-" + hashlib.md5(location).hexdigest().lower() + ".git"
    request_dir = tempfile.gettempdir()
    request_path = os.path.join(request_dir, request_filename)
    ## f = tempfile.mkstemp(suffix = '.git', prefix='-x-github-queue-', text=True)
    f = open(request_path, "w")
    f.write(location)
    f.flush()
    f.close()
    
    print "Content-Type: text/plain; charset=utf-8"
    print "Content-Disposition: inline"
    print ""
    print "Your request has been queued."
except Exception:
    serve_error()