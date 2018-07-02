import hashlib
import base64
from lockfile import FileLock, LockTimeout
from time import gmtime


def my_lock(LockFile, TimeOut = 3):
        lock = FileLock(LockFile)
	print "I locked", lock.path

        IsLock = False
        try:
                lock.acquire(timeout = TimeOut)    # wait up to 60 seconds
                IsLock = True
        except LockTimeout:
                IsLock = False
        
        if IsLock :
                return lock
        else:
                raise LockBusyException("Lock is busy")
        
class LockBusyException(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)       
 
 
def my_release(lock): 
        print "release, ", lock.path
	if lock is None :
               return False
        lock.release()
        return True
