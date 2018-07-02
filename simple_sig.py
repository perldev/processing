import os
import signal

def call_bad_function(d):
   return call_bad_function(d*d)
def sig_handler(signum, frame):
    print "segfault"

signal.signal(signal.SIGSEGV, sig_handler)

os.kill(os.getpid(), signal.SIGSEGV)

while True:
    call_bad_function(2)





