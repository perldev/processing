import traceback
from blockchain.wallet import Wallet
import blockchain.util
from blockchain.exceptions import APIException
import urllib2
import httplib
import random
import json
def get_balance( Adr, Confs=0 ):
    Url = "https://blockchain.info/q/addressbalance/{0}?confirmations={1}".format(Adr, Confs)

    Decoder = json.JSONDecoder()
    D = urllib2.urlopen(Url)
    Str = D.read()
    return  int(Str)
 

def process_out():
	blockchain.util.TIMEOUT = 660
        Crypton = Wallet("eb836197-285e-44ee-a8cf-5642a02e6250","#Prikol13_",api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        print "Crypton"
        (balance, balance_) = 0, 0
        for addr in Crypton.list_addresses():
		balance1=get_balance(addr.address)	
                print addr.address, addr.balance, balance1
                balance+= addr.balance
                balance_+= balance1
               
        print "Balance:"
        print balance
        print balance_





process_out()
