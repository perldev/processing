from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from  main.finance import   notify_admin_withdraw
from main.models import CryptoTransfers, Currency, Accounts, crypton_in, sato2Dec
from sdk.crypto import CryptoAccount
from sdk.crypto_settings import Settings as CryptoSettings
import traceback
import crypton.settings 


import urllib2
import time
import json

from main.my_cache_key import my_lock, my_release, LockBusyException
from main.api import  format_numbers_strong
from django.db import connection
from decimal import getcontext
import os
import sys




class Command(BaseCommand):
    args = '<Stock Title ...>'
    help = 'every minute get stock prices and save it to StockStat'

    def handle(self, *args, **options):
        
        Time =  0   
        try :
              Time = int(args[0])
        except :
              Time = 0  
        print "from %i " % (Time)
	LOCK = "incomin_btc_blockchaint_txid"
	lock = None
	try:
                lock = my_lock(LOCK)        
		process_block_info(Time)
	
	except LockBusyException as e:
               print "operation is locked", e.value
	except :
		print "Unexpected error:",str( sys.exc_info())
		traceback.print_exc(file=sys.stdout)
	finally:
	        my_release(lock)
	
       
def process_block_info(Time):
       
        user_system =   User.objects.get(id = 1)
        CurrencyInstance = Currency.objects.get(title = "BTC")
        getcontext().prec = crypton.settings.TRANS_PREC
        LastBlock = get_last_block()
        print "current block height is %i " % (LastBlock)
        AccountList = Accounts.objects.filter(currency = CurrencyInstance ).order_by('balance')
        OwnAccounts = {}
        for i in AccountList:
                OwnAccounts[i.reference] = i
	MissTranses = [
		"b7985ff9ae2c031d2a1a2aa2864036dff423e4a7e226f20ae6a05b8d10f12162",
		"e362eff1219e019a5891d288d3fbd6121ae127e3149f5566d8d3aebd71bd418e",
		"2f0d76ce32f5e182ebd0793dbd8000ea4e70b56c14462b4a32dd1bcb83621c32",
		"ffd420f3b20d516e44039cbae5a92d894258cadf7b6223ebd8b77e7b7bdcbc2e",
		"f661f7282a0280c0a8a73938c2726a9da8ab95f3ad17bd1fb8abccd76e510782",
		"5281dc88bed3f694e9968446d9003b68aa45bc4a6822f256a1d2c0d01c57fd29",
		"9c7d126f79f6e956c8de771fe585b3f6159f5df40fbccf1c3c33cdca0e853095"]

	ForAccount = "1KRgYSAChvP5UFUQBQfqAHih2kEYW1CThD"
	

        for Trans in MissTranses :
                time.sleep(1) 
                print "process adress %s" % (Trans)
		trans = None
                trans = get_trans(Trans)

                Txid = trans["hash"]
                    
                if  trans["time"]<Time:
                    print "this trans is old"
                    continue
                        
                print str(trans)
                        
                try :
                    Confirmations = LastBlock - trans["block_height"] + 1
                except :
                    continue
                        
                if is_out(trans["inputs"], OwnAccounts) : 
                      print "it is out trans for us %s" % (Txid)
                      continue
                        
                        
                try:
                    Decimal = get_in_acc(trans["out"], ForAccount )
                except :
                    print "get error during processing the %s" % trans
                    continue
                        
                if Decimal == 0:
                    print "it is out trans for %s " % (ForAccount)
                    continue
                        
                print "confirmations %i" % ( Confirmations )                        
                print " amount of %s" % (Decimal )
		TransObj = None
		try :
                    TransObj = CryptoTransfers.objects.get(crypto_txid = Trans, account = ForAccount)
                    print "trans %s is existed to %s  amnt %s %i"  % (TransObj.crypto_txid, TransObj.user.username, TransObj.amnt, TransObj.id)
		    print "it's not a missed trans"
		    continue  	
		    
                except  CryptoTransfers.DoesNotExist:
		    suffix = ForAccount[:-10]
                    print "trans %s  to save  %s  amnt %s" % (Trans.hash, output.address, Decimal)
                    TransObj =  CryptoTransfers(crypto_txid = Trans+"_"+suffix,
                                                status="processing",
                                                amnt = Decimal,
                                                currency = CurrencyInstance ,
                                                account = ForAccount,
                                                user = OwnAccounts[ ForAccount ],
                                                confirms = 0
                                                )
                    TransObj.save()
               

                

                print "#%i receive %s to %s amount of %s" % (Trans.id, Txid, Trans.user.username,  Trans.amnt )
                print "this trans is %s" % ( Trans.status )
 		continue
		if Trans.status == "processing" or Trans.status == "created":     
                           print "update confirmations"
                           Trans.status = "processing"
                           Trans.confirms = Confirmations
                           Trans.save()
       
 	        if Confirmations >= CryptoSettings["BTC"]["min_confirmation"] and Trans.status!= "processed":
                           Trans.confirms = Confirmations
                           crypton_in(Trans, user_system)
                           Trans.status = "processed"
                           Trans.save()
                                        
def get_trans( Adr ):
    Url = "https://blockchain.info/tx/%s?format=json" % (Adr)
    Decoder = json.JSONDecoder()
    D = urllib2.urlopen(Url)
    Str = D.read()        
    Res = Decoder.decode(Str)
    return Res

def is_out(Trans, OwnAccounts ):
   print str(Trans)
	
   for i in Trans:
        	if OwnAccounts.has_key( i["prev_out"]["addr"] ) :


	           return  True

   return False

def get_in_acc(Trans, Address):    
    Sum = 0    
    for i in Trans:
        if i["addr"] == Address :
           print "receive %i" % (i["value"])
           
           Sum = Sum + i["value"]
           
    return sato2Dec(Sum)
    
    
    
def get_last_block():
        Url = "https://blockchain.info/blocks?format=json"
        Decoder = json.JSONDecoder()
        D = urllib2.urlopen(Url)
        Str = D.read()        
        Res = Decoder.decode(Str)
        return Res["blocks"][0]["height"]
        
