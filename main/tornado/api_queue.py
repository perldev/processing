# -*- coding: utf-8 -*-

from decimal import Decimal, getcontext
import logging
import traceback
import time
# from tornaduv import UVLoop
import sys
import Queue   
from main.models import Trans
from main.account import Account, get_account
from crypton import settings

        
# DO NOT USE for highload operations
####make a queue demon here there only for back capability 
def add_fake_trans(TransMem, From, Amnt, Currency, To, order, status="created"):
    TransPrecession = settings.TRANS_PREC     
    trans = None
    if isinstance(From, Account):   
        NewBalance = To.balance + Amnt      
        trans = Trans(balance1=TransMem.balance1,
                      balance2=NewBalance,
                      user1=From.acc(),
                      user2=To,
                      out_order_id=order,
                      currency_id=Currency,
                      amnt=Amnt,
                      status=status,
                      res_balance1 = TransMem.res_balance1,
                      res_balance2 = NewBalance)
        To.balance = NewBalance
        To.save()       
    else:
        NewBalance = From.balance - Amnt
        
        trans = Trans(balance1=From.balance,
                       balance2=TransMem.balance1,
                       user1=From,
                       user2=To.acc(),
                       out_order_id=order,
                       currency_id=Currency,
                       amnt=Amnt,
                       status=status,
                       res_balance1 = NewBalance,
                       res_balance2 = TransMem.res_balance1 )
        From.balance = NewBalance
        From.save()
        
    trans.save()


         
def process_delayed_operation(item):
   
   if item[0] == 'deposit':
        process_deposit(item)
        
   if item[0] == 'order_cancel':
        process_cancel_order(item)
        
   if item[0] == 'deal':
        process_deal_order(item)
        
        
# put2queue(('deal', trans1, TradePair, OrderBuy))
# put2queue(('deal', trans2, TradePair, OrderSell))
             
def process_deal_order(item):
    (Type, Trans, Market, Order) = item
    From = Trans[1]
    if Trans[3] == Market.currency_on.id:
        # type sell
        Comission = get_account(user_id=settings.COMISSION_USER, currency_id=Market.currency_on.id)
        add_fake_trans(Trans[0], Market.transit_on, -1*Trans[2], Trans[3], From, Order.id, 'deal')
        add_fake_trans(Trans[0], From, -1*Trans[0].comission, Trans[3], Comission.acc(), Order.id, 'comission')
    else:
        Comission = get_account(user_id=settings.COMISSION_USER, currency_id=Market.currency_from.id)
        add_fake_trans(Trans[0], Market.transit_from, -1*Trans[2], Trans[3], From,  Order.id, 'deal')  
        add_fake_trans(Trans[0], From, -1*Trans[0].comission, Trans[3], Comission.acc(), Order.id, 'comission')
        
    print "process deal"
    print "="*60

#def add_fake_trans(From, Amnt, Currency, To, order, status="created"):
    
    
def process_cancel_order(item):
    (Type, Trans, Market, Order) = item
    print "="*60
    #(trans, From, Amnt, Currency, To, Comis) = Trans
    From = Trans[1]
    if Trans[3] == Market.currency_on.id:
        # type cancel sell
        add_fake_trans(Trans[0], Market.transit_on, -1*Trans[2], Trans[3], From, Order.id,  'order_cancel')
    else:
        add_fake_trans(Trans[0], Market.transit_from, -1*Trans[2], Trans[3], From, Order.id,  'order_cancel')    
   
    print "process cancel order" 
    print "="*60
            
       
def process_deposit(item):
    (Type, Trans, Market, Order) = item
    From = Trans[1]
    print "="*60
    #(trans, From, Amnt, Currency, To, Comis) = Trans
    if Trans[3] == Market.currency_on.id:
        # type sell
        add_fake_trans(Trans[0], From, Trans[2], Trans[3], Market.transit_on, Order.id,  'deposit')
    else:
        add_fake_trans(Trans[0], From, Trans[2], Trans[3], Market.transit_from,  Order.id, 'deposit')    
    
    print "process deposit order"
    print "="*60
    # if TradePair.currency_on.id == order.curre
        
   