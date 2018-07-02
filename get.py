from blockchain.blockexplorer import get_address
from sdk.crypto import CryptoAccount
import time
with open("keys1") as f:
    L = f.readlines()
    Sum = 0
	
    Dict = {} 
    for address in L: 
	if Dict.has_key(address):
		continue

	address = address.replace("\n","")
	Dict[address]=1
	
	D = CryptoAccount("BTC")
	#Res = get_address(address)
	print "%s,%s" % (address,D.dumpprivkey(address))
	#print address
    	#print Res.final_balance
	
	#Sum += Res.final_balance
	#time.sleep(1)

