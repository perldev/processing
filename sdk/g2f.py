#!/usr/bin/env python
import base64
import hashlib
import hmac
import os
import time
import struct
from main.models import TransError
appName = "BTC_TRADE_UA"

def newSecret():
    Rand1 = os.urandom(20)
    return (base64.b32encode(Rand1), base64.b16encode(Rand1).lower() )

def getQRLink(name, secret):
    return "https://www.google.com/chart?chs=150x150&chld=M|0&cht=qr&chl=otpauth://totp/{0}-{1}%3Fsecret%3D{2}".format(name, appName, secret)


def auth(s_secret, nstr):
    # raise if nstr contains anything but numbers
    int(nstr)
    Time = time.time()
    tm = int(Time / 30)
    secret = base64.b32decode(s_secret)
    # try 30 seconds behind and ahead as well
    codes = []
    for ix in [-6,-5,-4,-3,-2,-1, 0, 1, 2,3,4,5,6]:
        # convert timestamp to raw bytes
        b = struct.pack(">q", tm + ix)
        # generate HMAC-SHA1 from timestamp based on secret key
        hm = hmac.HMAC(secret, b, hashlib.sha1).digest()
        # extract 4 bytes from digest based on LSB
        offset = ord(hm[-1]) & 0x0F
        truncatedHash = hm[offset:offset+4]
        # get the code from it
        code = struct.unpack(">L", truncatedHash)[0]
        code &= 0x7FFFFFFF
        code %= 1000000
        Res = "%06d" % code
        codes.append(Res)
        if Res == nstr:
            return True
    raise TransError("%s time -  %s" % (nstr, Time ) )
    return False

def main():
    # Setup
    name = raw_input("Hi! What's your name? ")
    pw = raw_input("What's your password? ")
    (secret, secret2) = newSecret() # store this with the other account information
    link = getQRLink(name, secret)
    print("Please scan this QR code with the Google Authenticator app:\n{0}\n".format(link))
    print("For installation instructions, see http://support.google.com/accounts/bin/answer.py?hl=en&answer=1066447")
    print("\n---\n")

    # Authentication
    opw = raw_input("Hi {0}! What's your password? ".format(name))
    if opw != pw:
        print("Sorry, that's not the right password.")
    else:
        code = raw_input("Please enter your authenticator code: ")
        if auth(secret, code):
            print("Successfully authenticated! Score!")
        else:
            print("Sorry, that's a fail.")

if __name__ == "__main__":
    main()
