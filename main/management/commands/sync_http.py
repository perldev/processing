from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from main.models import CryptoTransfers, Currency, Accounts, Orders, Deals, add_trans, TradePairs
from django.db import transaction
import sys
from main.api import  format_numbers_strong
from django.db import connection
from decimal import getcontext
from main.my_cache_key import my_lock, my_release, LockBusyException
import os
import sys, traceback
import time
from crypton import settings
import tornado.web
from main.http_common import caching
from decimal import Decimal
import logging
logger_application = logging.getLogger('tornado.application')
import threading

class TornadoServer(object):

    _instance = None

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            raise RuntimeError('core is not created')
        return cls._instance

    @classmethod
    def is_created(cls):
        return cls._instance is not None

    @classmethod
    def create_instance(cls, *args):
        logger_application.info('creatpring tornado instance')
        cls._instance = TornadoServer(*args)
        logger_application.info('core created: {0}'.format(cls._instance))
        return cls._instance


    def __init__(self, *args):
        self.port = args[0]
        self.application = tornado.web.Application(args[1])
        self.keys4delete = [] 
        self.cache = caching()    


    # start eventloop, webserver and periodic reading
    def start(self):
        self.application.listen(self.port)
     
        self.main_loop = tornado.ioloop.IOLoop.instance()
        self.main_loop.start()

def lock_global(Val):
    print "==="*12
    print "LOCK GLOBAL"
    print Val
    print "==="*12

class StopHandler(tornado.web.RequestHandler):
    def get(self):
        logger_application.info("stoping tornado")
        tornado.ioloop.IOLoop.instance().stop()
      

def my_async(func2decorate):
    def wrapper(*args, **kwards):
        callable_object = lambda: func2decorate(*args, **kwards)
        threading.Thread(target=callable_object).start()
        return True
    return wrapper

@my_async
def delete_tornado_cache(t, keys):
    print "delete all cache"
    s = TornadoServer.get_instance()
    cache = s.cache
    start = time.time()
    cache = caching()
    keys.append("state") 
    cache.delete_many(keys)
    print "setup cache state"
    #cache.set("state", t, 60000)
    print "delete all cache timing"
    end = time.time()
    print  end-start       

@my_async
def delete_user_state(i, start_time):
    print "delete user state"
    s = TornadoServer.get_instance()
    cache = s.cache
    start = time.time()
    session = cache.get("user_"+str(i))
    cache.delete("session_"+str(i))
    print "user view session"
    print session
    if not session is None:
        cache.delete("balance_"+session)
        print "setup new"
        print start_time
        # cache.delete("session_"+str(i), start_time, 60000)
       
    end = time.time()
    print "delete user  timing"
    print  end-start       

class AddTransForPayIn(tornado.web.RequestHandler):

    def get(self, order_id):
        start = time.time()
        order = Orders.objects.get(id=order_id, status="processing")
        s = TornadoServer.get_instance()
        try:
          with transaction.atomic():
            
               add_trans(order.transit_1, order.sum2, order.currency1,
                         order.transit_2, order, "payin", str(order), False)
               order.status = "processed"
               order.save()
               try:
                  i=order.user_id
                  s.keys4delete.append("balance_"+str(i))
                  print "got trans from %i" % i
               except: 
                  traceback.print_exc()
                  print "problem in working with cache"
          end = time.time()
          print "add trans payin timing"
          print  end-start       
          self.write({"status": True, "time": end-start})
        except:
            traceback.print_exc()
            order.status = "core_error"
            print "add trans payin timing"
            end = time.time()
            print  end-start       
            order.save()
            self.set_status(500)


class AddTransForWithdraw(tornado.web.RequestHandler):

    def get(self, order_id):
        start = time.time()
        order = Orders.objects.get(id=order_id, status="processing")
        s = TornadoServer.get_instance()
        try:
          with transaction.atomic():

               add_trans(order.transit_1, order.sum1, order.currency1,
                         order.transit_2, order,
                        "withdraw", str(order), False)

               order.status = "processed"
               order.save()
               try:
                  i=order.user_id
                  s.keys4delete.append("balance_"+str(i))
                  print "got trans from %i" % i
               except:
                  traceback.print_exc()
                  print "problem in working with cache"
          end = time.time()
          print "add trans payin timing"
          print  end-start
          self.write({"status": True, "time": end-start})
        except:
            traceback.print_exc()
            order.status = "core_error"
            print "add trans withdraw timing"
            end = time.time()
            print  end-start
            order.save()
            self.set_status(500)


 


class AddTransForHandler(tornado.web.RequestHandler):

    def get(self, order_id):
        start = time.time()
        order = Orders.objects.get(id=order_id, status="created")
        s = TornadoServer.get_instance()
        try:
          with transaction.atomic():
            
               FromAccount = Accounts.objects.get(user = order.user, currency = order.currency1)
               add_trans(FromAccount, order.sum1_history, order.currency1,
                         order.transit_1, order, "deposit")
               order.status = "processing"
               order.save()
               cache = caching()
               try:
                  i=order.user_id
                     
                  s.keys4delete.append("balance_"+str(i))
                  delete_user_state(i, start)                  
                  print "got trans from %i" % i
                  Title = order.trade_pair.url_title
                  CachedKey1 = 'client_orders_' + str(i) + "_" + Title
                  CachedKey2 = 'balance_' + str(i)
                  s.keys4delete.append(CachedKey1)
                  s.keys4delete.append(CachedKey2)
                  s.keys4delete.append("buy_list_" + Title)
                  s.keys4delete.append("sell_list_" + Title)
               except: 
                  traceback.print_exc()
                  print "problem in working with cache"
          end = time.time()
          print "add trans timing"
          print  end-start       

          self.write({"status": True, "time": end-start})
        except:
            traceback.print_exc()
            order.status = "core_error"
            print "add trans timing"
            end = time.time()
            print  end-start       
            order.save()
            self.set_status(500)

 

class DefaultHandler(tornado.web.RequestHandler):
    def get(self):
        start = time.time()
        cache = caching() 
        with transaction.atomic():
            remove_orders()
            process_deals(start, cache)
        
        s = TornadoServer.get_instance()
        if len(s.keys4delete)>0:
           delete_tornado_cache(start, s.keys4delete) 
           print s.keys4delete
           s.keys4delete = []
           
        end = time.time()
        print "="*64
        print  end-start       
        print "="*64
        self.write({"status": True, "time": end-start})       

application_urls = [
    (r'/sync', DefaultHandler),
    (r'/add_trans/(\d+)', AddTransForHandler),
    (r'/add_payin/(\d+)', AddTransForPayIn),
    (r'/add_withdraw/(\d+)', AddTransForWithdraw),
    (r'/stop', StopHandler)
]
                                        



class Command(BaseCommand):
    args = '<Stock Title ...>'
    help = 'start api tornado server'

    def handle(self, *args, **options):
#        setup_logging()

        worker = TornadoServer.create_instance(8090, application_urls, False)
        worker.start()




def process_deals(t, cache):
      for deal in Deals.objects.filter(status="processing")[:100]:
	    process_deal(deal, t, cache)

def process_deal(deal, t, cache):
    s = TornadoServer.get_instance()
    print "process order deal %i" % deal.id
    order=None
    try :
        order = deal.order2
    except:
        print "i cant find order %i" % deal.order2_id
        deal.status="core_error"
        deal.save()
        return
    try:        
        Title = order.trade_pair.url_title
        s.keys4delete.append("balance_" + str(order.user_id))
        s.keys4delete.append("sell_list_" + Title)
        s.keys4delete.append("deals_list_" + Title)

 
        Account = Accounts.objects.get(user_id = order.user_id, currency_id = order.currency2_id)
        add_trans(order.transit_2,
                deal.amnt,
                order.currency2,
                Account,
                order,
                "deal",
                str(deal.order1_id)
                )
        
        add_trans(Account,
                deal.amnt*Decimal("0.0005"),
                order.currency2,
                order.transit_2,
                order,
                "comission",
                str(deal.order1_id)
                )

        if order.sum1/order.sum1_history<0.0001:
          order.status='processed'
          order.save()
        deal.trade_pair_id = order.trade_pair.id
        deal.user2_id = order.user_id
        deal.user1_id = deal.order1.user_id
        deal.status="processed"
        deal.save()
    except:
        deal.status="core_error"
        deal.save()

    delete_user_state(order.user_id, cache)
    try:
        session = cache.get("user_"+str(order.user_id))
        if not session is None:
             s.keys4delete.append("balance_"+session)
    #    cache.delete("session_"+str(order.user_id), t, 60000)
    except:
        traceback.print_exc()    
    # add notification

def remove_orders():
    for order in Orders.objects.filter(status="canceling")[:100]:
         print "removing order %i" % order.id
         __inner_remove_order(order)



def __inner_remove_order(Order2Remove):
    if Order2Remove.trade_pair.status != 'processing':
       return False;
    s = TornadoServer.get_instance()
    start = time.time() 
    count_up  = Orders.objects.filter(id = Order2Remove.id, status="canceling" ).update(status='canceled')
    if count_up<1:
       return False
    Title = Order2Remove.trade_pair.url_title
    i = Order2Remove.user.id
    delete_user_state(i, start)                  
    CachedKey1 = 'client_orders_' + str(i) + "_" + Title
    CachedKey2 = 'balance_' + str(i)
    s.keys4delete.append(CachedKey1)
    s.keys4delete.append(CachedKey2)
    s.keys4delete.append("buy_list_" + Title)
    s.keys4delete.append("sell_list_" + Title)

    Account = Accounts.objects.get(user = Order2Remove.user, currency = Order2Remove.currency1)
    add_trans(Order2Remove.transit_1,
              Order2Remove.sum1,
              Order2Remove.currency1,
              Account,
              Order2Remove,
              "order_cancel")



def self_check():
        print "check UAH" 
        CurrencyInstance = Currency.objects.get(id=1)
        check_orders_by_pairs(CurrencyInstance)
        print "check BTC" 
        CurrencyInstance = Currency.objects.get(id=2)
        check_orders_by_pairs(CurrencyInstance)
        print "="*60
        print "check orders"
        if 1 and  check_currency_orders(CurrencyInstance):
               print "lock BTC"
               lock_global("orders_inconsistense_btc" )
        print "="*60        

        CurrencyInstance = Currency.objects.get(id=3)
        print "check %s" % CurrencyInstance.title

        if check_currency_orders(CurrencyInstance, 0.2):
               print "lock LTC orders"
               lock_global("orders_inconsistense_"+CurrencyInstance.title )
        print "="*60        
        CurrencyInstance = Currency.objects.get(id=4)
        print "check %s" % CurrencyInstance.title

        if 1 and check_currency_orders(CurrencyInstance, 0.15):
               print "lock NVC orders"
               lock_global("orders_inconsistense_"+CurrencyInstance.title )
        print "="*60        

        CurrencyInstance = Currency.objects.get(id=5)
         
        print "="*60        
        if 1 and  check_currency_orders(CurrencyInstance):
               print "lock DASH  orders"
               lock_global("inconsistense_"+CurrencyInstance.title )
        
        print "="*60        
        CurrencyInstance = Currency.objects.get(id=7)
        print "check 7 %s" % CurrencyInstance.title
        if 0 and  check_currency_orders(CurrencyInstance):
               print "lock PPC orders"
               lock_global("inconsistense_"+CurrencyInstance.title )
        
       
        print "="*60        
        CurrencyInstance = Currency.objects.get(id=14)

        if  check_currency_orders(CurrencyInstance):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )
        
        print "="*60        
        
        CurrencyInstance = Currency.objects.get(id=8)
        print "check 8  %s" % CurrencyInstance.title

        print "="*60        
        
        CurrencyInstance = Currency.objects.get(id=9)
        print "check 9 %s" % CurrencyInstance.title
        print "="*60        
        if 1 and  check_currency_orders(CurrencyInstance):
               print "lock DOGE orders"
               lock_global("orders_inconsistense_" + CurrencyInstance.title )
        
        CurrencyInstance = Currency.objects.get(id=12)
        print "check 12  %s" % CurrencyInstance.title
        if 0 and not check_crypto_balance(CurrencyInstance) :
               print "lock %s" % CurrencyInstance.title
               lock_global("inconsistense_"+CurrencyInstance.title )
               return
                

        if 0 and check_currency_orders(CurrencyInstance):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )
         
        print "="*60        
        CurrencyInstance = Currency.objects.get(id=15)
        if 1 and check_currency_orders(CurrencyInstance):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )

        print "="*60        
        CurrencyInstance = Currency.objects.get(id=16)
        print "check 16 %s" % CurrencyInstance.title
        if 1 and check_currency_orders(CurrencyInstance, 1):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )
        print "="*60
        CurrencyInstance = Currency.objects.get(id=10)
        print "check 10 %s" % CurrencyInstance.title

        if 1 and check_currency_orders(CurrencyInstance, 0.001):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )

        print "="*64
        CurrencyInstance = Currency.objects.get(id=18)
        print "check 18 %s" % CurrencyInstance.title

        if 1 and check_currency_orders(CurrencyInstance, 0.001):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )        


        print "="*60
        CurrencyInstance = Currency.objects.get(id=17)
        print "check 17 %s" % CurrencyInstance.title

        if 1 and check_currency_orders(CurrencyInstance, 1):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )
        
        print "="*60
        CurrencyInstance = Currency.objects.get(id=19)

        if 1 and check_currency_orders(CurrencyInstance, 0.01):
               print "lock %s" % CurrencyInstance.title
               lock_global("orders_inconsistense_" + CurrencyInstance.title )

    
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



def check_orders_by_pairs(Cur):
    cursor = connection.cursor()
    transit_accounts = []
    trade_pairs = []
    for pair in TradePairs.objects.filter(status="processing", currency_on=Cur):
        transit_accounts.append(str(pair.transit_on.id))
        trade_pairs.append(str(pair.id))
        Query = "SELECT sum(sum1) FROM main_orders \
                 WHERE currency1_id=%s\
                 AND status=\"processing\"  \
                 AND user_id not in (346)  and trade_pair_id=%i" % ( str(Cur.id), pair.id )
        cursor.execute(Query, [])
        OrdersSum = cursor.fetchone() * 1
        if OrdersSum == (None, ):
            OrdersSum = Decimal("0.0")
        else:
            OrdersSum = OrdersSum[0]
        print " Trade in %s -> %s on orders %s on account %s delta is - %s" % (pair.currency_on, pair.currency_from,
                                                                               OrdersSum, pair.transit_on.balance,
                                                                               OrdersSum - pair.transit_on.balance,
                                                                               )
    print "="*64
    trade_pairs = []
    for pair in TradePairs.objects.filter(status="processing", currency_from=Cur):
        transit_accounts.append(str(pair.transit_from.id))
        trade_pairs.append(str(pair.id))
        Query = "SELECT sum(sum1) FROM main_orders \
                 WHERE currency1_id=%s\
                 AND status=\"processing\"  \
                 AND user_id not in (346)  and trade_pair_id=%i " % ( str(Cur.id), pair.id )
        cursor.execute(Query, [])
        OrdersSum = cursor.fetchone() * 1
        if OrdersSum == (None, ):
            OrdersSum = Decimal("0.0")
        else:
            OrdersSum = OrdersSum[0]
        print " Trade in %s -> %s on orders %s on account %s(%i) delta is - %s " % (pair.currency_on, pair.currency_from,
                                                                                OrdersSum, pair.transit_from.balance,
                                                                                pair.transit_from.id,
                                                                                OrdersSum - pair.transit_from.balance,
                                                                               )


