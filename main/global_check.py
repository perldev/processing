# -*- coding: utf-8 -*-

from main.models  import Accounts, Currency, TradePairs, sato2Dec, change_volitile_const
from blockchain.wallet import Wallet
from sdk.crypto import CryptoAccount
from sdk.crypto_krb import CryptoAccountKrb, PREC as PREC_KRB 
import crypton.settings
from sdk.crypto_settings import Settings as CryptoSettings
import json
import requests
import blockchain.util
import urllib2
import main.msgs
'''
 <h3>Мы должны: {{item.currency}} <h3>
 <p>На ордерах: {{item.sum}} {{item.currency}} </p>
 <p>Ошибка: {{item.mistake}} {{item.currency}} </p>
 <p>Комиссия: {{item.comission}} {{item.currency}} </p>
 <p>Сальдо ввод - вывод: {{item.saldo}} </p> 
'''
import crypton.settings as settings
from django.db import connection
from decimal import Decimal
from sdk.p24 import p24


from main.models import VolatileConsts

def lock_user(User):
    lock = VolatileConsts(Name="user_lock",
                          Value=User.username)
    lock.save(using="security")

def check_approve(obj):
    try:
        VolatileConsts.objects.using("security").get(Name="approve_trans",
                                    Value=str(obj.id))
        return True
    except:
        return False

def approve_trans(obj):
    approve = VolatileConsts(Name="approve_trans",
                          Value=str(obj.id))
    approve.save(using="security")


def check_lock_user(username):
    try:
        l = list(VolatileConsts.objects.using("security").filter(Name="user_lock", Value=username))
        return len(l)>1
    except:
        return False




def check_global_lock():
	try :
		l = list(VolatileConsts.objects.using("security").filter(Name = "global_lock"))
		return len(l)>2
	except :
		return False

def lock_global(Desc):
	lock = VolatileConsts(Name = "global_lock", Value = Desc)
	lock.save(using = "security")

def check_uah_balance():
        cursor = connection.cursor()
        cursor.execute("SELECT sum(balance) FROM main_accounts WHERE currency_id=1 AND balance>0 AND balance<1000000 AND id!=353 ");
        s = cursor.fetchone()*1
        if s == (None, ) :
              s = Decimal("0.0")
        else:
           (s, ) = s
        cursor.execute("SELECT sum(amnt)*0.99 FROM main_cardp2ptransfers WHERE status in ('created','processing','processing2','auto') AND pub_date>='2015-05-08' ");

        s1 = cursor.fetchone()*1
        if s1 == (None, ) :
              s1 = Decimal("0.0")
        else:
           (s1, ) = s1

        D = p24("UAH", "https://api.privatbank.ua/", settings.P24_MERCHID2, settings.P24_PASSWD2, settings.P24MERCH_CARD2)
        D1 = p24("UAH", "https://api.privatbank.ua/", settings.P24_MERCHID, settings.P24_PASSWD, settings.P24MERCH_CARD)
        BalanceUAH  = Decimal(D.balance() ) + Decimal(D1.balance())
        return (BalanceUAH - s - s1+16200)>0


def check_btc_balance(verbose=False):
        cursor = connection.cursor()
        cursor.execute("SELECT sum(balance) FROM main_accounts WHERE currency_id=2 AND balance>0 ");
        s = cursor.fetchone()*1
        if s == (None, ) :
              s = Decimal("0.0")
        else:
           (s, ) = s
	main_account = Accounts.objects.get(id=13)	
        
        blockchain.util.TIMEOUT = 300

        cursor.execute("SELECT sum(if(debit_credit='in',-1*amnt, amnt)) "
		       "FROM main_cryptotransfers WHERE status in ('processing','created','processing2')   AND currency_id=2 AND pub_date>='2015-05-08' " );

        s1 = cursor.fetchone()*1
        if s1 == (None, ) :
              s1 = Decimal("0.0")
        else:
           (s1, ) = s1
        SERVICE_URL = settings.blockchaininfo_service
	(Balance1, Balance2, Balance3, Balance4, Balance5, Balance6, Balance8) = (0, 0, 0, 0, 0, 0, 0)
        Balance7 = 0
        Balance9 = 0
        Balance10 = 0
        Balance11 = 0
	Balancecold  = sato2Dec(get_balance("1AMTTKEAav9aQDotyhNg4Z7YSUBYTTA6ds",0))
        Balancecold  = sato2Dec(get_balance("19jHRHwuHnQQVajRrW976aCXYYdgij8r43",0)) + Balancecold 
        Balancecold  = sato2Dec(get_balance("17iAu7iSSwo9VGeNn6826Lz1qLPq152xAW",0)) + Balancecold 
        Balancecold  = sato2Dec(get_balance("15c3H6jhQys8b8M5vszx2s21UNDH3caz9P",0)) + Balancecold 
        Balancecold  = sato2Dec(get_balance("19YxpMLUAdZoJpUBqwURcJzd2zs4knMvGV",0)) + Balancecold 
        
	Balance1  = sato2Dec(get_balance("167GWdfvG4JtkFErq4qBBLqKYFK26dhgDJ",0)) + Balance1 
        Balance1  = sato2Dec(get_balance("1Q1woBCCGiuELYzVvS3hCgSs6pFKuqHNpt",0)) + Balance1 
        Balance1  = sato2Dec(get_balance("19TaiL4j288Zgm1AQXUwMcyLup7vki54Fs",0)) + Balance1 
        Balance1  = sato2Dec(get_balance("13EDdpizTP3grQQAnpCtSJNTTwkDkV9VeB",0)) + Balance1 
        Balance1  = sato2Dec(get_balance("1AXKnEK3P1tiHEBAVpDzg4k3yXosR5oKL8",0)) + Balance1 
        Balance1  = sato2Dec(get_balance("1GjthoqTvBq1N8KkKVEDHV9b8snmt2ehcS",0)) + Balance1 
        Balance1  = sato2Dec(get_balance("1LvDnHktCL77r16eimv7Fr9d5xDieb1wFC",0)) + Balance1 
        Balancecold  = sato2Dec(get_balance("15jsdKn3L8ExQngY8HRRUz3prof8mAn8yr",0)) + Balancecold
        HotWalletBalance  = sato2Dec(get_balance("1LNYCGkXtJscvMHHucEfpxWMBnf33Ke18W",0))
 
         
	Crypton = Wallet("2b835907-d012-4552-830c-6116ab0178f2","#Prikol13_", service_url=SERVICE_URL, api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
	Crypton1 = Wallet("772bb645-48f5-4328-9c3d-3838202132d6","xxx_21_34_Zb", service_url=SERVICE_URL,  api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
	Crypton2 = Wallet("ee23c1bd-d3dd-4661-aef5-8e342c7f5960","xxx_21_34_Zb", service_url=SERVICE_URL, api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
 	Crypton3 = Wallet("e6202826-bb24-435c-8350-b4a942b4380b","xxx_21_34_Zb", service_url=SERVICE_URL, api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
 	Crypton4 = Wallet("3ccaa767-770f-476f-a836-9db1c005055e","_quenobi8610", service_url=SERVICE_URL, api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
 	Crypton5 = Wallet("caa19b23-198a-4aad-a9c0-3f80efe37118","dirty_43_13", service_url=SERVICE_URL, api_code="b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton6 = Wallet("14ef48bb-4d71-4bc4-be34-75ba0978202f","dirty_43_13", service_url=SERVICE_URL, api_code= "b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton7 = Wallet("913d6442-fc77-4b7b-b5f8-af272e458897","xxx_21_34_Zb", service_url=SERVICE_URL, api_code= "b720f286-9b3f-452c-b93c-969c8dd3967f")
        Crypton8 = Wallet("5432b01c-f67e-473e-aa4c-29cd9682b259","xxx_21_34_Zb", service_url=SERVICE_URL, api_code="b720f286-9b3f-452c-b93c-969c8dd3967f") # 
        Crypton9 = Wallet("a2ba7138-2bd3-4898-b68b-d0908d40bc4d",
                         "xxx_21_34_Zb",
                         api_code = "b720f286-9b3f-452c-b93c-969c8dd3967f", service_url=SERVICE_URL) # 

        Crypton10 = Wallet("d8d5ce8a-6ff9-4f7e-80f3-08cac5788781",
                         "xxx_21_34_Zb",
                         api_code="b720f286-9b3f-452c-b93c-969c8dd3967f",service_url=SERVICE_URL) # 

  
        Crypton11 = Wallet("eb836197-285e-44ee-a8cf-5642a02e6250",
                         "#Prikol13_",
                          api_code = "b720f286-9b3f-452c-b93c-969c8dd3967f",service_url=SERVICE_URL) # 
        Crypton12 = Wallet("c800e14e-95d4-4fcf-816b-696fbaaf5741",
                        "xxx_21_34_Zb",api_code="b720f286-9b3f-452c-b93c-969c8dd3967f",service_url=SERVICE_URL)
            
        Crypton13 = Wallet("e60c37e7-4375-44ea-b167-a63b453c14a1",
                        "#Prikol13_",api_code="b720f286-9b3f-452c-b93c-969c8dd3967f", service_url=SERVICE_URL)
            
        Crypton14 = Wallet("118344b4-5d26-4cfe-871a-0c3393ee5db0",
                        "#Prikol13_",api_code="b720f286-9b3f-452c-b93c-969c8dd3967f", service_url=SERVICE_URL)
        Crypton15 = Wallet("f252bb25-6b99-4e49-a5cf-41489eefb728",
                        "#Prikol13_",api_code="b720f286-9b3f-452c-b93c-969c8dd3967f", service_url=SERVICE_URL)
        Crypton16 = Wallet("5a778945-fbb4-4692-b448-fd5b513c008d",
                        "#Prikol13_",api_code="b720f286-9b3f-452c-b93c-969c8dd3967f", service_url=SERVICE_URL)
        Balance2 = sato2Dec(Crypton.get_balance())
	print "Balance of hot wallet 1 " +  str(Balance2)
        

        Balance3 = sato2Dec(Crypton1.get_balance()) + sato2Dec(Crypton4.get_balance())
	print "Balance of hot wallet 2 "  + str(Balance3)
        Balance4 = sato2Dec(Crypton2.get_balance())
	print "Balance of hot wallet 3 "  + str(Balance4)
        Balance5 = sato2Dec(Crypton3.get_balance())
	print "Balance of hot wallet 4 "  + str(Balance5)
        Balance6 = sato2Dec(Crypton5.get_balance())
	print "Balance of hot wallet 5 "  + str(Balance6)
        Balance7 = sato2Dec(Crypton6.get_balance())
	print "Balance of hot wallet 6 "  + str(Balance7)
	Balance8 = sato2Dec(Crypton7.get_balance()) 
	print "Balance of hot wallet 7 "  + str(Balance8)
    
        Balance9 = sato2Dec(Crypton8.get_balance())
	print "Balance of hot wallet 8 "  + str(Balance9)
        Balance10 = sato2Dec(Crypton9.get_balance())
	print "Balance of hot wallet 9 "  + str(Balance10)
         
        Balance11 = sato2Dec(Crypton10.get_balance())
	print "Balance of hot wallet 10 "  + str(Balance11)
        
        Balance12 = sato2Dec(Crypton11.get_balance())
	print "Balance of hot wallet 12 "  + str(Balance12)

        Balance13 = sato2Dec(Crypton12.get_balance())
	print "Balance of hot wallet 13 "  + str(Balance13)
        Balance14 = sato2Dec(Crypton13.get_balance())
	print "Balance of hot wallet 14 "  + str(Balance14)
        Balance15 = sato2Dec(Crypton14.get_balance())
	print "Balance of hot wallet 15 "  + str(Balance15)

        Balance16 = sato2Dec(Crypton15.get_balance())
	print "Balance of hot wallet 16 "  + str(Balance16)
        Balance17 = sato2Dec(Crypton16.get_balance())
	print "Balance of hot wallet 17 "  + str(Balance17)
	Dismiss = Decimal("0.0")
        Crypton = CryptoAccount("BTC", "trade_stock")
        LChange = Crypton.listaddressgroupings()
        BalanceCore = Decimal(str(Crypton.getbalance()))
        if False:
          for adres in LChange[0]:
               if not  adres[0] in ( "1LNYCGkXtJscvMHHucEfpxWMBnf33Ke18W",
				    "1CzLixrLpf6LRiiqH5jMZ7dD3GP2gDJ4xw", 
                                    "1FLCVHDDwJmimjgch5s4CtjpbNn5pQ3mAi"):
                    BalanceCore += Decimal(str(adres[1]))



	BalanceOnHots = BalanceCore + Balance11 + Balance10 + Balance1  + Balance2 + Balance3 + Balance4 + Balance5 + Balance6 + Balance7 + Balance8 + Balance9 + Balance12 + Balance13 + Balance14 + Balance15 + Balance16 + Balance17
	
        print "our core wallet " +  str(BalanceCore)
        print "Correction " +  str(Dismiss)
	print "balance of cold wallet " + str(Balancecold)
	print "balance on hots wallet " + str(BalanceOnHots)
        print "balance of accounts " + str(s)
	print "main accounts balance " + str(main_account.balance)
	print "checking consistens %s" % (s+main_account.balance) 
	print "balance of processing  " +  str(s1)
	print "sum on walletes " + str(Balancecold+BalanceOnHots)
	print "sum in system " + str(s1+s)
        change_volitile_const("balance_corr_BTC", Dismiss)
        change_volitile_const("balance_out_BTC", str(Balancecold+BalanceOnHots))


	Delta = Balancecold + BalanceOnHots - s - s1 + Dismiss
	print "Delta is %s " % Delta
        return Delta>=0

def get_balance(addr, Confs=0):
    Res = get_adress(addr)
    print int(Res["final_balance"])
    return int(Res["final_balance"])

def get_balance1( Adr, Confs=0 ):
    Url = "https://blockchain.info/q/addressbalance/{0}?confirmations={1}".format(Adr, Confs)

    Decoder = json.JSONDecoder()
    D = urllib2.urlopen(Url)
    Str = D.read()
    print Str
    return  int(Str)

def get_adress( Adr ):
    Url = "https://blockchain.info/address/%s?format=json" % (Adr)

    Decoder = json.JSONDecoder()
    D = urllib2.urlopen(Url)
    Str = D.read()
    Res = Decoder.decode(Str)
    return Res

def check_crypto_balance(Currency, Correction =  "0", check_wallet=True):
        cursor = connection.cursor()
        cursor.execute("SELECT sum(balance) FROM main_accounts WHERE currency_id=%i AND balance>0" % Currency.id);
        s = cursor.fetchone()*1
        if s == (None, ) :
              s = Decimal("0.0")
        else:
           (s, ) = s

        cursor.execute("SELECT sum(amnt) FROM main_cryptotransfers WHERE debit_credit='out' \
			AND status in ('processing','processing2','created') AND pub_date>='2015-05-08' and currency_id=%i " % Currency.id);

        s1 = cursor.fetchone()*1
        if s1 == (None, ) :
              s1 = Decimal("0.0")
        else:
           (s1, ) = s1
        
        cursor.execute("SELECT sum(amnt) FROM main_cryptotransfers WHERE debit_credit='in' \
			AND status in ('processing', 'processing2') AND confirms>0 AND pub_date>='2015-05-08' and currency_id=%i " % Currency.id);

        s2 = cursor.fetchone()*1
        if s2 == (None, ) :
              s2 = Decimal("0.0")
        else:
           (s2, ) = s2

        Crypton = None
        Balance = None
        if check_wallet:
          if Currency.title in ("KRB",):
  
            Crypton = CryptoAccountKrb(Currency.title, "trade_stock")
            Balance  = Crypton.getbalance()

          if Currency.title in ("XMR",):
              rpc_url = CryptoSettings[Currency.title]["host"]
              req =  {"jsonrpc":"2.0","method":"getbalance", "id":1}
              resp = requests.post(rpc_url, data=json.dumps(req) )
              print resp.json() 
              Balance = float(resp.json()["result"]["balance"])/PREC_KRB
              Balance = "%.12f" % ( Balance )
         
          if Currency.title in ("ZEC", "BCH"):

            Crypton = CryptoAccount(Currency.title, "")
            Balance  = Crypton.getbalance()
         

          if Currency.title in ("LTC","NVC", "DOGE", "ITI", "DASH", "PPC", "CLR", "SIB" ):
   
            Crypton = CryptoAccount(Currency.title, "trade_stock")
        
            Balance  = Crypton.getbalance()

          change_volitile_const("balance_corr_"+Currency.title, Correction)
          change_volitile_const("balance_out_"+Currency.title, str(Balance))
	print "balance in system %s" % s
	print "balance on wallet " + str(Balance)
	print s1+s
        if check_wallet:
	  Delta = (Decimal(Balance) - s1 - s - s2  + Decimal(Correction))
	  print "Delta is %s " % Delta
          return Delta>0
        return True





def check_crypto_currency(Cur, Eps="0.01"):
       
        Main_Account = Accounts.objects.get(user_id = settings.CRYPTO_USER, currency = Cur)
        cursor = connection.cursor()
        transit_accounts = []
        for pair  in TradePairs.objects.all():
            transit_accounts.append(str(pair.transit_on.id))
            transit_accounts.append(str(pair.transit_from.id))
        
        ComisId = settings.COMISSION_USER
        
        NotId = ",".join(transit_accounts)
        #not Credit and not Mistake and not transit accounts
        Query =  "SELECT sum(balance) FROM main_accounts \
                    WHERE currency_id=%s \
                    AND user_id not in (346, 31, %s) AND id not in (%s) AND balance>0 " % (str(Cur.id), ComisId, NotId)
                    
        cursor.execute(Query, [])
        S1 = cursor.fetchone()
        if S1 == (None, ) :
                S1 = Decimal("0.0")
        else :
                S1 = S1[0]
                
        Query = "SELECT sum(sum1) FROM main_orders \
                        WHERE currency1_id=%s AND currency2_id!=currency1_id \
                        AND status=\"processing\"  \
                        AND user_id not in (346)  " % (str(Cur.id))   
                        
        cursor.execute(Query, [  ])
        
        S2 = cursor.fetchone()*1
        if S2 == (None, ) :
                S2 = Decimal("0.0")
        else :
                S2 = S2[0]
        print S1
        print S2
        CheckSum  = S1 + S2
        print "balance in system "
        print CheckSum
        print "balance on wallet"
        print Main_Account.balance
        print "div between two sums "
        print CheckSum + Main_Account.balance
        if CheckSum <= abs(Main_Account.balance):
            return False
        else :
            return True	


def check_currency_orders(Cur, Eps=0.01):
    
        cursor = connection.cursor()
        transit_accounts = []
        trade_pairs = []
        for pair  in TradePairs.objects.filter(status = "processing", currency_on = Cur):
            transit_accounts.append( str( pair.transit_on.id ) )
            trade_pairs.append( str( pair.id ) )

            
        for pair  in TradePairs.objects.filter(status = "processing", currency_from = Cur):
            transit_accounts.append( str( pair.transit_from.id ) )
            trade_pairs.append( str( pair.id ) )

            
        ComisId =  settings.COMISSION_USER
        InId = ",".join(transit_accounts)
        TradesId = ",".join(trade_pairs)
        Query = "SELECT sum(balance) FROM main_accounts WHERE  id IN (%s)  " % (InId)
        #print Query
        cursor.execute(Query, [])
            
        TransitSum = cursor.fetchone()*1
        if TransitSum == (None, ) :
                TransitSum = Decimal("0.0")
        else :
                TransitSum = TransitSum[0]  
        Query = "SELECT sum(sum1) FROM main_orders \
                        WHERE currency1_id=%s AND currency2_id!=currency1_id \
                        AND status=\"processing\"  \
                        AND user_id not in (346) AND trade_pair_id in (%s) " % ( str(Cur.id), TradesId )        
        #print Query
        cursor.execute(Query, [])
        
        OrdersSum = cursor.fetchone()*1
        if OrdersSum == (None, ) :
                OrdersSum = Decimal("0.0")
        else :
                OrdersSum = OrdersSum[0]
        print "on orders"       
        print OrdersSum
	print "on accounts"
        print TransitSum
   	print "Delta transit sum %s" % (TransitSum-OrdersSum)  
        if TransitSum < OrdersSum  :
	    print "case 1"
            return True
        else :
	    print "case 2"
            if  OrdersSum - TransitSum > Eps :
                return True
            else :
                return False

		

def check_fiat_currency(Cur):
        cursor = connection.cursor()
        pay_in_out = []
        for pair  in TradePairs.objects.filter( currency_on = Cur, currency_from  = Cur):
            pay_in_out.append(str(pair.transit_on.id))
            pay_in_out.append(str(pair.transit_from.id))
            
        ComisId =  settings.COMISSION_USER
        MainIn = ",".join(pay_in_out)
        Query = "SELECT sum(balance) FROM main_accounts WHERE  in (%s) " % (MainIn)
        #not Credit and not Mistake and not transit accounts
        cursor.execute(Query, [])
            
        WholeSum = cursor.fetchone()*1
        if  WholeSum == (None, ) :
                WholeSum = Decimal("0.0")
                
        transit_accounts = []
        for pair  in TradePairs.objects.all():
            transit_accounts.append(str(pair.transit_on.id))
            transit_accounts.append(str(pair.transit_from.id))
            
        ComisId =  settings.COMISSION_USER
        NotId = ",".join(transit_accounts)
        #not Credit and not Mistake and not transit accounts
        Query = "SELECT sum(balance) FROM main_accounts WHERE currency_id=%s \
                            AND user_id not in (346, 31) AND id not in (%s) AND balance>0 " % (str(Cur.id), NotId)
        cursor.execute(Query, [])
            
        S1 = cursor.fetchone()*1
        if S1 == (None, ) :
                S1 = Decimal("0.0")
        
        Query = "SELECT sum(sum1) FROM main_orders WHERE currency1_id=%s AND currency2_id!=currency1_id \
                                                AND status=\"processing\"  \
                            AND user_id not in (346)  " % ( str(Cur.id) )
        cursor.execute(Query, [])
        
        S2 = cursor.fetchone()*1
        if S2 == (None, ) :
                S2 = Decimal("0.0")
        print S1
        print S2
        print Main_Account.balance
        if S1 + S2 < WholeSum:
            return check_currency_orders(Cur)
        else :
            return True 
        
        
        
