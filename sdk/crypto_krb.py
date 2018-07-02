import requests
from sdk.crypto_settings import Settings
import hashlib
import json
PREC = 1000000000000

class CryptoAccountKrb:
        def __init__(self, currency="KRB", account=None):
           self.__currency =  currency
           self.__host = Settings[currency]["host"]
           self.__port = Settings[currency]["port"]
           self.__rpc_user = Settings[currency]["rpc_user"]
           self.__rpc_pwd = Settings[currency]["rpc_pwd"]
           self.__change_address= Settings[currency]["change_address"]
           self.__access = "http://%s:%s/json_rpc" % (self.__host, self.__port)

        def walletpassphrase(self, time=20):
            raise Exception("Is not implemented")

        def keypoolrefill(self, size=None):
            raise Exception("Is not implemented")

        def getrawmempool(self):          
            raise Exception("Is not implemented")

        def getrawtransaction(self, txid):          
             req = {"jsonrpc":"2.0", "method": "getTransaction", "params": {"transactionHash": txid}}
             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             return  respJson["result"]["transaction"]
             
      
        def decoderawtransaction(self, hex_data):
            raise Exception("Is not implemented")

        def listaddressgroupings(self):
             """
             curl -d '{"jsonrpc": "2.0","method": "getAddresses", "params": {}}' -v http://10.9.0.18:8050/json_rpc
             """
             req = {"jsonrpc":"2.0", "method": "getAddresses", "params": {}}
             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             
             return  respJson["result"]["addresses"]

        def walletlock(self):
            raise Exception("Is not implemented")

        def dumpwallet(self, filename):
            raise Exception("Is not implemented")

        def backupwallet(self, filename):
            raise Exception("Is not implemented")

   	def dumpprivkey(self, Addr):
            raise Exception("Is not implemented")

        def getstatus(self):
            
             req = {"jsonrpc":"2.0", "method": "getStatus", "params": {}}
             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             return  respJson["result"]


        def getbalance(self):
            
             req = {"jsonrpc":"2.0", "method": "getBalance", "params": {}}
             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             print respJson 
             return  float(respJson["result"]["availableBalance"])/PREC  + float(respJson["result"]["lockedAmount"])/PREC
            

        def getnewaddress(self):
             req = {"jsonrpc":"2.0", "method": "createAddress", "params": {}}
             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             return  respJson["result"]["address"]
            

        def listunspent(self):
            raise Exception("Is not implemented")
       
        def sendtoaddress(self, to_addr):
            raise Exception("Is not implemented")
 
        def listtransactions(self, block_count=1, from_block=1,verbose=False, addresses=None):
             """
            {"jsonrpc":"2.0","result":{"items":[{"blockHash":"4474c76e14d0dc03213a41861726a37e6d9f3a5d982f3cbcfa680d32650ad52d","transactions":[]},{"blockHash":"3e0089bcaf7f5bc5a808c4aaf88ccae479280f255c1237566c460a59ab9d28e3","transactions":[]}]}}krb@bitcoin:~$ 
            '{"jsonrpc": "2.0","method": "getTransactions", "params": { "blockCount":2, "firstBlockIndex": 121300}}'

             """ 

             req = {"jsonrpc":"2.0", "method": "getTransactions", "params": {"blockCount":block_count, "firstBlockIndex":from_block }}
             if addresses:
                req["params"]["addresses"] = addresses
             if verbose :
                print json.dumps(req)

             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             if verbose :
                print respJson
             result = []
             for i in respJson["result"]["items"]:
                 for item in i["transactions"]:
                   result.append(item)
             return  result
              
    
        def sendmany(self, addrs, changeto=None, fee=0.005, payment_id=None):       
             if changeto is None:
                changeto = self.__change_address

             if payment_id is None:
                m = hashlib.md5()
                m.update(str(addrs))
                payment_id = m.hexdigest()
             
             transfers = []
             for item in addrs:
                amnt = item["amount"]
                key = item["account"]
                transfers.append({"amount": int(amnt*PREC), 
                                    "address": key
                                    })

             
             fee = int(fee*PREC)

             req = {"jsonrpc":"2.0", "method": "sendTransaction", 
                    "params": 
                    {'fee':fee, 
                     'anonymity':0,
                      'unlockTime':0,
                     'paymentId': payment_id, 
                     "changeAddress":changeto, 
                     "transfers": transfers} }
             print req
             resp = requests.post(self.__access, data=json.dumps(req))
             respJson = resp.json()
             print respJson
             return  respJson["result"]["transactionHash"]
            

              
