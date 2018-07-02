#!/usr/bin/env python
import os
import sys
from datetime import datetime
import traceback

if __name__ == "__main__":
    parent_dir = os.path.abspath(os.path.dirname(__file__)) # get parent_dir pat
    LOCK =  "_".join(sys.argv[1:])	
    print "time of working %s" % (datetime.now())
    try:
    	sys.path.append(parent_dir)
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crypton.settings")
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
    except :
        print "Unexpected error:", str(sys.exc_info())
        print('-'*60)
        traceback.print_exc(file=sys.stdout)
        print('-'*60)


    

