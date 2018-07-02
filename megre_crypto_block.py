from blockchain.wallet import Wallet
import blockchain.util
from blockchain.exceptions import APIException
import urllib2
import httplib
import random
from decimal import Decimal
import traceback 

def process_out():
	blockchain.util.TIMEOUT = 660

        Crypton = Wallet("2b835907-d012-4552-830c-6116ab0178f2","#Prikol13_","068Anna", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton1 = Wallet("772bb645-48f5-4328-9c3d-3838202132d6","xxx_21_34_Zb","Kenobi8910", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton2 = Wallet("ee23c1bd-d3dd-4661-aef5-8e342c7f5960","xxx_21_34_Zb","Kenobi8910", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton3 = Wallet("e6202826-bb24-435c-8350-b4a942b4380b","xxx_21_34_Zb", "Kenobi8910", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton4 = Wallet("3ccaa767-770f-476f-a836-9db1c005055e","_quenobi8610", "second_creation_34", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton5 = Wallet("caa19b23-198a-4aad-a9c0-3f80efe37118","dirty_43_13","second_creation_34", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton6 = Wallet("14ef48bb-4d71-4bc4-be34-75ba0978202f","dirty_43_13", "second_creation_34", api_code= "b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton7 = Wallet("913d6442-fc77-4b7b-b5f8-af272e458897","xxx_21_34_Zb", "Kenobi8910", api_code= "b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton8 = Wallet("5432b01c-f67e-473e-aa4c-29cd9682b259","xxx_21_34_Zb", "Kenobi8910", api_code="b720f286-9b3f-452c-b93c-969c8dd3967f") # 
        wallets = [Crypton, Crypton1, Crypton2, Crypton3, Crypton4, Crypton5, Crypton6, Crypton7, Crypton8 ]
        MergAdress = "19jHRHwuHnQQVajRrW976aCXYYdgij8r43" 
        while True:
            
            for item in  range(0,len(wallets)):
                wallet = wallets[item]
                Balance = sato2Dec(wallet.get_balance())
                print "Balance of hot wallet %i %s " %  (item, str(Balance))
            
            line = raw_input('merge it ?')
            if line == 'yes':
               
               index = raw_input('from which ?')
                 
               wallet = wallets[int(index)] 
              
               amnt = raw_input('how much ?')
               fee = raw_input('Fee ?')
               print "send to  %s amount %i with fee %i" % (MergAdress, 100000000*float(amnt), 100000000*float(fee))
               try:  
                  Txid = wallet.send_many({
                         MergAdress: 100000000*float(amnt)
                         }, fee=100000000*float(fee))#, from_address = "18ySCLDfCD7qjUmDXgqArbHbPpwrGwVEDa");

                  print "txid %s" % (Txid.tx_hash)
               except:
                  traceback.print_exc()
            line = raw_input('thats all?')
            if line == 'yes':
               break

def sato2Dec(Satochi):
    PreStr = list(str(int(Satochi)))
    size = len(PreStr)
    Prec = 8
    if size > Prec:
        Dot = size - Prec
        return Decimal("".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
    else:
        Mask = ['0'] * Prec
        From = Prec - size
        Mask[From:] = PreStr
        return Decimal("0." + "".join(Mask))


process_out()
