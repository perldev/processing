#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    parent_dir = os.path.abspath(os.path.dirname(__file__)) # get parent_dir path
    sys.path.append(parent_dir)
    
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crypton.settings")
    from main.models import Msg
    for i in Msg.objects.all().order_by("id"):
	print " %s -%s " % (i.pub_date, i.text)

