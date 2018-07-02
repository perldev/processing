# -*- coding: utf-8 -*-

import json
from decimal import Decimal, getcontext
import logging
import traceback
import calendar
import time
import tornado.ioloop
# from tornaduv import UVLoop
import sys
import Queue    
import copy

import tornado.web
# import tornaduv
# import pyuv
import threading
# Create your views here.


from django.template import Context, loader
from crypton.http import HttpResponse
from crypton import settings
from django.utils.translation import ugettext as _
from django.utils import formats

from django.db import connection
from django.contrib.auth.models import User
from main.models import UserCustomSettings, VolatileConsts, OrdersMem, Accounts, TradePairs, Orders, Trans, Currency, \
    Msg, add_trans, TransError, StockStat, OnlineUsers

from main.api_http_common import caching, cached_json_object, my_cache, status_false, json_auth_required, check_api_sign
from main.api_http_common import format_numbers10, format_numbers_strong, format_numbers, format_numbers4, \
    json_false500, json_true

    

from datetime import datetime, timedelta
from main.account import get_account

logger_application = logging.getLogger('tornado.application')

from main.models import dictfetchall, to_prec, OrderTimer, add_trans2, DealsMemory
from  main.msgs import system_notify

from main.my_cache_key import my_lock, LockBusyException, check_freq, my_release

from crypton.http import MemStore
from main.tornado.api_queue import process_delayed_operation 


class TornadoServer(object):
    # статический экземпляр этого класса, всегда один
    # доступ к нему только через TornadoServer.get_instance()
    _instance = None

    @classmethod
    def get_instance(cls):
        """
        Возвращает экземпляр ядра, если оно создано.
        :rtype : Core
        """
        if not cls._instance:
            raise RuntimeError('core is not created')
        return cls._instance

    @classmethod
    def is_created(cls):
        """
        Создано ли ядро?
        :rtype : bool
        """
        return cls._instance is not None

    @classmethod
    def create_instance(cls, *args):
        """
        Создаёт и возвращает объект 
        :rtype : Core
        """
        logger_application.info('creatpring tornado instance')
        cls._instance = TornadoServer(*args)
        logger_application.info('core created: {0}'.format(cls._instance))
        return cls._instance


    def __init__(self, *args):
        self.port = args[0]
        self.application = tornado.web.Application(args[1])
        self.queue_enabled = args[2]
        # self.core_event_loop = pyuv.Loop.default_loop()
        self.memstore = MemStore.create_instance(is_local=False)
        SizeQueue  = 5000
        SubscribeCountRead = 100
        self.queue1 = Queue.Queue(SizeQueue)
        self.task_archive = tornado.ioloop.PeriodicCallback( lambda: processed_orders2deals(), 1000*20)
        self.task_memtrans2trans = tornado.ioloop.PeriodicCallback( lambda: process_queue(self.queue1, SubscribeCountRead, process_delayed_operation), 500)
        
        
        # tornado.ioloop.IOLoop.configure(UVLoop)
        # tornado.ioloop.IOLoop.current().initialize(self.core_event_loop)

    # start eventloop, webserver and periodic reading
    def start(self):
        self.application.listen(self.port)
        if self.queue_enabled:
            self.task_archive.start()
            self.task_memtrans2trans.start()

        self.main_loop = tornado.ioloop.IOLoop.instance()        
        self.main_loop.start()

def put2queue(some_object):
    backend  = TornadoServer.get_instance()
    try:
        backend.queue1.put(copy.deepcopy(some_object), False)
        return  True
    except Queue.Full:
        logger_application.error("="*60)
        logger_application.error("WARNING")        
        logger_application.error("so sad there is not avalible slot")
        return False
    except:
        logger_application.critical(traceback.format_exc())
        
        
class StopHandler(tornado.web.RequestHandler):
    def get(self):
        logger_application.info("stoping tornado")
        tornado.ioloop.IOLoop.instance().stop()

        
        
# user_id = models.IntegerField()
# type_deal = models.CharField(max_length=40, choices=TYPE, default='buy', verbose_name=u"Тип")
# user = models.CharField(max_length=255, verbose_name=u"Username")
# price = models.DecimalField(max_digits=20,
# blank=True,
# decimal_places=10, verbose_name=u"цена")

                                    #decimal_places=10, verbose_name=u"сумма в базовой валюте")
    #amnt_trade = models.DecimalField(max_digits=20,
                                     #blank=True,
                                     #decimal_places=10, verbose_name=u
    #amnt_base = models.DecimalField(max_digits=20,
                                    #blank=True,"сумма в валюты торга")
    #pub_date = models.DateTimeField(auto_now=True, verbose_name=u"Дата ")
    #trade_pair = models.IntegerField(verbose_name=u"Валютная пара")

    
# transaction from the deals to     




    
   

def cache_control(Req):
    do = Req.REQUEST.get("do", None)
    cache = caching()

    if do == "flush":
        return json_false500(Req)

    if do == "get":
        key = Req.REQUEST.get("key")
        return HttpResponse(str(cache.get(key,"")))

    if do == "del":
        key = Req.REQUEST.get("key")
        value = str(cache.get(key,""))
        cache.delete(key)
        return HttpResponse(value)

    return json_false500(Req)        

    
def canceled_orders2deals(Order2Remove):
    (amnt_base, amnt_trade) = (0, 0)  
    if  (Order2Remove.sum1_history - Order2Remove.sum1)>0:
        
        if Order2Remove.type_deal == "sell" :
                amnt_base = (Order2Remove.sum1_history - Order2Remove.sum1 )* Order2Remove.price
                amnt_trade = Order2Remove.sum1_history - Order2Remove.sum1
                
        if Order2Remove.type_deal == "buy":
                amnt_base = Order2Remove.sum1_history - Order2Remove.sum1 
                amnt_trade = (Order2Remove.sum1_history - Order2Remove.sum1)/Order2Remove.price
                    
        user =  User.objects.get(id = Order2Remove.user)
        
        
        deal = DealsMemory(type_deal = Order2Remove.type_deal,
                           user = user.username,
                           user_id = Order2Remove.user,
                           price = Order2Remove.price, 
                           amnt_base = amnt_base, 
                           amnt_trade = amnt_trade,
                           trade_pair = Order2Remove.trade_pair)
                           
        deal.save()    
    
    
    
def processed_orders2deals():
    logger_application.info("cache deals")
    for item in OrdersMem.objects.filter(status="processed"):
         (amnt_base, amnt_trade) = (0,0)
         if item.type_deal == "sell" :
            amnt_base = item.sum1_history * item.price
            amnt_trade = item.sum1_history
         if item.type_deal == "buy":
            amnt_base = item.sum1_history 
            amnt_trade = item.sum1_history/item.price
                  
         if item.type_deal == "transfer":
            item.archive()
            continue
        
         user =  User.objects.get(id = item.user)
         deal = DealsMemory(type_deal = item.type_deal,
                            user = user.username,
                            user_id = item.user,
                            price = item.price, 
                            amnt_base = amnt_base, 
                            amnt_trade = amnt_trade,
                            trade_pair = item.trade_pair)
         deal.save()
         
         item.archive()
         item.delete()
    
def process_queue(q, read_count, function_to_process=None):
    logger_application.info("process inner queue")
    
    for i in xrange(1, read_count):
        
        try:
            item = q.get(False)            
            if function_to_process:
                function_to_process(item)
        
            q.task_done()
        except Queue.Empty:
            return True
        except:
            logger_application.critical("something wrong with process queue \n" + traceback.format_exc() )
            
    
    
def my_async(func2decorate):
    def wrapper(*args, **kwards):
        callable_object = lambda: func2decorate(*args, **kwards)
        threading.Thread(target=callable_object).start()
        return True
    return wrapper


def deposit_funds(Order, currency1):
    return _(u"Deposit funds  %(sum)s %(currency)s according with order #%(order_id)i " % {
              'sum': Order.sum1_history,
              'currency': currency1.title,
              'order_id': Order.id})


def order_canceled(Order):
    return _(u"You order #%(order_id)i is canceled" % {'order_id': int(Order)})
              
              
def order_finish(Order):
    return _(u"You order #%(order_id)i is fully completed" % {'order_id': Order.id})


def order_return_unused(Order, Currency1, AccumSumToSell):
    return _(u"Return %(sum).8f %(currency)s unused funds according with order #%(order_id)i  " %
             {'sum': AccumSumToSell,
              'currency': str(Currency1),
              'order_id': Order.id})


def order_description_buy(Sum1, Sum2, Order, BackOrder, TradePair):
    Price = BackOrder.price

    return _("Buying %(sum).8f %(currency)s according with order  #%(order_id)i, price %(price).8f total sum  %(total).8f" %
                 {'sum': Sum1,
                  'currency': str(TradePair.currency_on),
                  'order_id': BackOrder.id,
                  'price': Price,
                  'total': Sum2
                  })
  
def order_description_sell(Sum1, Sum2, Order, BackOrder, TradePair):
    Price = Order.price
    return _("Selling  %(sum).8f %(currency)s according with order #%(order_id)i, price %(price).8f total sum  %(total).8f " %
                 {'sum': Sum1,
                  'currency': str(TradePair.currency_on),
                  'order_id': Order.id,
                  'price': Price,
                  'total': Sum2
                  })

# process order  item that match order  AccumSumToSell=>7000UAH  AccountBuyer BTC  Accountc
# OrderBuy order of buying BTC sum1 is for exmaple 1 BTC , OrderSell 7000UAH  selling
# OrderSell - is a source order
# Account seller is a source account
def process_order_buy(AccountSeller,  AccumSumToSell, OrderBuy, OrderSell, TradePair):
     ## TODO move to settings for every user
    logger_application.info("="*120)
    logger_application.info(OrderSell)
    logger_application.info("="*120)
    logger_application.info(AccountSeller) 
    logger_application.info("buy %s " % (AccumSumToSell))
    logger_application.info(OrderBuy)
    logger_application.info("="*120)

    # TODO add salt verify, notify me
    if False and not OrderBuy.verify(str(OrderBuy.user)):
        logger_application.critical("Sign FAILED %s" % str(OrderBuy))
        return  AccumSumToSell

    # OrderBuy.sum1*OrderBuy.price
    # 1.9 *7000  = 13000 UAH
    # OrderBuySum  UAH for BTC
    OrderBuySum = OrderBuy.sum1*OrderBuy.price
    if OrderBuySum > AccumSumToSell:
        logger_application.info("buy case  1")
        ## a danger of low overflow
        TransSum = AccumSumToSell/OrderBuy.price
        AccountBuyer = get_account(user_id=OrderBuy.user, currency_id=OrderSell.currency1)
        ##comission
        trans1 = add_trans2(AccountBuyer,
                            AccumSumToSell*-1,
                            OrderSell.currency1,
                            OrderSell,
                            "deal",
                            True, 
                            OrderBuy.comission)

        trans2 = add_trans2(AccountSeller,
                            TransSum*-1,
                            OrderBuy.currency1,
                            OrderBuy,
                            "deal",
                            True, 
                            OrderSell.comission)
        # TODO move to queue

        try:
            put2queue(('deal', trans1, TradePair, OrderBuy))
            put2queue(('deal', trans2, TradePair, OrderSell))
            
            system_notify_async(order_description_sell(TransSum, OrderBuySum, OrderBuy, OrderSell, TradePair),
                                AccountBuyer.get_user())
                                
            system_notify_async(order_description_buy(TransSum, OrderBuySum, OrderBuy, OrderSell, TradePair),
                                AccountSeller.get_user())
        except:
            logger_application.critical("something gooing wrong with notification" + traceback.format_exc())
            pass
        
        return 0

    if OrderBuySum <= AccumSumToSell:
        logger_application.info("buy case  2")
        TransSum = OrderBuy.sum1
        AccountBuyer = get_account(user_id=OrderBuy.user, currency_id=OrderSell.currency1)
        ##comission

        trans1 = add_trans2(AccountBuyer,
                            OrderBuySum*-1,
                            OrderSell.currency1,
                            OrderSell,
                            "deal",
                            True,
                            OrderBuy.comission)

        trans2 = add_trans2(AccountSeller,
                            TransSum*-1,
                            OrderBuy.currency1,
                            OrderBuy,
                            "deal",
                            True, 
                            OrderSell.comission)
        # TODO move to queue
        try:
            put2queue(('deal', trans1, TradePair, OrderBuy))
            put2queue(('deal', trans2, TradePair, OrderSell))
            system_notify_async(order_description_sell(TransSum, OrderBuySum, OrderBuy, OrderSell, TradePair),
                                    AccountBuyer.get_user())
            system_notify_async(order_description_buy(TransSum, OrderBuySum, OrderBuy, OrderSell, TradePair),
                                    AccountSeller.get_user())
            system_notify_async(order_finish(OrderBuy), AccountBuyer.get_user())

        except:
            logger_application.critical("somthing gooing wrong with notification" + traceback.format_exc())
            pass
        OrderBuy.make2processed()
        return AccumSumToSell-OrderBuySum


# process order  item that match order Order AccumSumToSell=>1BTC  AccountSeller UAH Accounts
# OrderBuy order of buying BTC sum1 is for exmaple 7000 UAH , OrderSell 1 BTC selling
def process_order_sell(AccountSeller,  AccumSumToSell, OrderBuy, OrderSell, TradePair):
    ## TODO move to settings for every user
    logger_application.info("=========================================================================================")
    logger_application.info(OrderSell)
    logger_application.info(AccountSeller)
    logger_application.info("sell %s" % (AccumSumToSell))
    logger_application.info(OrderBuy)
    logger_application.info("=========================================================================================")
    
    # TODO add salt verify, notify me
    if False and not OrderBuy.verify(str(OrderBuy.user)):
        logger_application.info("Sign FAILED %s" % str(OrderBuy))
        return  AccumSumToSell
    # 7000/3600 = 1.9 BTC
    OrderBuySum = OrderBuy.sum1/OrderSell.price
    if OrderBuySum > AccumSumToSell:
        ## a danger of low overflow
        logger_application.info("sell case  1")
        TransSum = AccumSumToSell*OrderSell.price
        
        AccountBuyer = get_account(user_id=OrderBuy.user, currency_id=OrderSell.currency1)
        ##comission
        
        trans1 =  add_trans2(AccountBuyer,
                             AccumSumToSell*-1,
                             OrderSell.currency1,
                             OrderSell,
                             "deal",
                             True,
                             OrderBuy.comission)

        trans2 = add_trans2(AccountSeller,
                           TransSum*-1,
                           OrderBuy.currency1,
                           OrderBuy,
                           "deal",
                           True,
                           OrderSell.comission)                   
        # TODO move to queue
        try:
            put2queue(('deal', trans1, TradePair, OrderSell))
            put2queue(('deal', trans2, TradePair, OrderBuy))
            
            system_notify_async(order_description_sell(AccumSumToSell, TransSum, OrderSell,  OrderBuy, TradePair),
                                AccountSeller.get_user())
            system_notify_async(order_description_buy(AccumSumToSell, TransSum, OrderSell, OrderBuy, TradePair),
                                AccountBuyer.get_user())
        except:
            logger_application.critical("something gooing wrong with notification" + traceback.format_exc())
            pass

        
        return 0

    if OrderBuySum <= AccumSumToSell:
        logger_application.info("sell case  2")
        TransSum = OrderBuy.sum1
        AccountBuyer = get_account(user_id=OrderBuy.user, currency_id=OrderSell.currency1)
        ##comission
        trans1 = add_trans2(AccountBuyer,
                            OrderBuySum*-1,
                            OrderSell.currency1,
                            OrderSell,
                            "deal",
                            True,
                            OrderSell.comission)
                            
        trans2 = add_trans2(AccountSeller,
                            TransSum*-1,
                            OrderBuy.currency1,
                            OrderBuy,
                            "deal",
                            True,
                            OrderBuy.comission)
        # TODO move to queue
        try:
            put2queue(('deal', trans1, TradePair, OrderSell))
            put2queue(('deal', trans2, TradePair, OrderBuy))
            system_notify_async(order_description_sell(OrderBuySum, TransSum, OrderSell, OrderBuy, TradePair), AccountSeller.get_user())
            system_notify_async(order_description_buy(OrderBuySum, TransSum, OrderSell, OrderBuy, TradePair), AccountBuyer.get_user())
            system_notify_async(order_finish(OrderBuy), AccountBuyer.get_user())

        except:
            logger_application.critical("somthing gooing wrong with notification" + traceback.format_exc())
            pass
        
        OrderBuy.make2processed()
        return AccumSumToSell - OrderBuySum

def admin_system_notify_async(cortage):
    pass


def auth(Req):
    Nonce = Req.REQUEST.get("nonce", None)
    if Nonce is None:
        return json_false500(Req)

    Sign = Req.META.get('HTTP_API_SIGN', None)

    if Sign is None:
        return json_false500(Req, {"description": "invalid_params", "key": "api_sign"})

    PublicKey = Req.META.get('HTTP_PUBLIC_KEY', None)
    if PublicKey is None:
        return json_false500(Req, {"description": "invalid_params", "key": "public_key"})

    try:
        Req.user = check_api_sign(PublicKey, Sign, Req.body)
        Cache = caching()
        Cache.set("nonce_" + PublicKey, int(Nonce), 50000)
        Nonce = Cache.get("nonce_" + PublicKey)
        return json_true(Req, {"nonce": Nonce, "public_key": PublicKey})
    except:
        logger_application.critical(traceback.format_exc())
        return json_false500(Req, {"description": "auth_faild"})


def make_auto_trade(OrderSell, TradePair, Price, Currency1, Sum1, Currency2):
    # if we sell
    # Query = "SELECT * FROM main_ordersmem  WHERE  trade_pair_id=%i" % (TradePair.id)
    logger_application.info("="*300)
    logger_application.info("call order")
    logger_application.info(OrderSell)
    
    if int(TradePair.currency_on.id) == int(Currency1.id):
        Query = "SELECT * FROM main_ordersmem  WHERE  currency1=%i AND trade_pair=%i \
                           AND status='processing' AND price >= %s  \
                           AND user!=%i  ORDER BY price DESC, id DESC" % (Currency2.id,
                                                                          TradePair.id,
                                                                          format_numbers_strong(Price), OrderSell.user)
    else:
        Query = "SELECT * FROM main_ordersmem WHERE  currency1=%i AND trade_pair=%i \
                           AND status='processing' AND price <= %s \
                           AND user!=%i  ORDER BY price, id DESC " % (Currency2.id,
                                                                      TradePair.id,
                                                                      format_numbers_strong(Price), OrderSell.user )

    List = OrdersMem.objects.raw(Query)
    # ##work on first case
    AccumSumToSell = Sum1
    AccountBuyer = get_account(user_id=OrderSell.user, currency_id=Currency2.id)
    UserDeals = [int(OrderSell.user)]
    process_order = None

    if TradePair.currency_on.id == Currency1.id :
        process_order = lambda AccountBuyer, AccumSumToSell, OrderBuy, OrderSell, TradePair: process_order_sell(AccountBuyer, AccumSumToSell, OrderBuy, OrderSell, TradePair)
    else:
        process_order = lambda AccountBuyer, AccumSumToSell, OrderBuy, OrderSell, TradePair: process_order_buy(AccountBuyer, AccumSumToSell, OrderBuy, OrderSell, TradePair)

    # TODO in case of exception block OrderSell and OrderBuy and interrupt the cycle
    for OrderBuy in List:
        UserDeals.append(int(OrderBuy.user))
        try :
            AccumSumToSell = process_order(AccountBuyer, AccumSumToSell, OrderBuy, OrderSell, TradePair)
            
        except TransError as e:
            logger_application.critical(traceback.format_exc())
            OrderBuy.status = "core_error"
            OrderSell.status = "core_error"
            OrderBuy.save()
            OrderSell.save()
            admin_system_notify_async((OrderBuy, OrderSell))
            ResultSum = finish_create_order(TradePair, AccumSumToSell, OrderSell)
            return {"start_sum": Sum1, "status":False, "last_sum": ResultSum, "users_bothered": UserDeals}


        if AccumSumToSell > 0.00000001:
            continue
        else:
            break

            
            
    logger_application.info("="*300)
    logger_application.info(AccumSumToSell)
    ResultSum = finish_create_order(TradePair, AccumSumToSell, OrderSell)
    OrderSell.sum1 = AccumSumToSell
    
    # comission operation
    
    if ResultSum < 0.00000001 and  ResultSum>=0:
         #if ResultSum != 0:
         #   return_rest2acc(OrderSell, AccumSumToSell, Currency1)

         OrderSell.sum1 = 0
         OrderSell.make2processed()
    else:
         OrderSell.save()

    return {"start_sum": Sum1, "status":True, "last_sum": ResultSum, "users_bothered": UserDeals}



@my_async
def system_notify_async(Msg, User):
    system_notify(Msg, User)


def finish_create_order(TradePair,  AccumSumToSell, Order):
    ##base currency
    if Order.currency1 == TradePair.currency_on.id:
        if AccumSumToSell < TradePair.min_trade_base:
            system_notify_async(order_finish(Order), Order.user)
            return 0
        else:
            return AccumSumToSell
    else:
        SumToBuy = AccumSumToSell/Order.price
        if SumToBuy < TradePair.min_trade_base:
            system_notify_async(order_finish(Order), Order.user)
            return 0
        else:
            return AccumSumToSell


@my_async
def reload_cache(Res, Type):
    cache = caching()
    DeleteKeys = []
    for i in Res["users_bothered"]:
        CachedKey1 = 'client_orders_' + str(i) + "_" + Type
        CachedKey2 = 'balance_' + str(i)
        DeleteKeys.append(CachedKey1)
        DeleteKeys.append(CachedKey2)
        # deal_list_btc_uah
    DeleteKeys.append("sell_list_" + Type)
    DeleteKeys.append("buy_list_" + Type)
    logger_application.info("delete this keys %s " % str(DeleteKeys))

    cache.delete_many(DeleteKeys)


def process_auto(Res, TradePair, Dict = None):
    Encoder = json.JSONEncoder()
    if Res["status"]:

        if Res["start_sum"] == Res["last_sum"]:
            Dict = {"status": True, "description": _("The order has been created")}

        elif Res["last_sum"] == 0:
            Dict = {"status": "processed",
                    "description": _("Your order has been fully processed successfully"),
                    "start_sum_to_buy": str(Res["start_sum"]),
                    "last_sum_to_buy": str(Res["last_sum"])
            }
        elif Res["start_sum"] > Res["last_sum"]:
            Dict = {"status": "processed", "description": _("Your order has been  processed partial"),
                    "start_sum_to_buy": str(Res["start_sum"]),
                    "last_sum_to_buy": str(Res["last_sum"])
            }
    else:
        Dict = {"status": "process_order_error", "description": _("The mistake has been occurred during"
                                                                  " creation of the order,"
                                                                  " and developers were notified about it")}
    Type = TradePair.url_title
    reload_cache(Res, Type)
    return Encoder.encode(Dict)


def process_mistake(Req, Mistake):
    Dict = None
    Encoder = json.JSONEncoder()

    if Mistake == 'incifition_funds':
        Dict = {"status": Mistake, "description": _(u"У вас недостаточно средств для этой операции,"
                                                    u" пополните ваш счет во вкладке "
                                                    u"<a href='/finance'> \"финансы\" </a> ")}
    elif Mistake == "MinCount":
        Dict = {"status": Mistake, "description": _("Count of deal is too small")}
    elif Mistake == "invalid_params":
        Dict = {"status": Mistake, "description": _("Invalid params")}
    else:
        Dict = {"status": Mistake, "description": _("Some mistake has been occured, "
                                                    "try later, or call support")}
    return Encoder.encode(Dict)


@my_cache()
def market_prices(Req):
    Dict = None
    Encoder = json.JSONEncoder()
    prices = []
    for item in TradePairs.objects.filter(status="processing").order_by("ordering"):
        TopName = item.url_title + "_top_price"
        Price = VolatileConsts.objects.get(Name=TopName)
        prices.append({"type": TopName, "price": Price.Value})
    RespJ = Encoder.encode({"prices": prices})
    return RespJ


@json_auth_required
def remove_order(Req, Order):
    Encoder = json.JSONEncoder()

    FreqKey = "orders" + str(Req.user)
    #if not check_freq(FreqKey, 3):
    #    Response = HttpResponse('{"status":false,  "description":"frequancy limit"}')
    #    Response['Content-Type'] = 'application/json'
    #    return Response

    if __inner_remove_order(Order, Req.user):
        system_notify_async(order_canceled(Order), Req.user)
        Dict = {"status": True}
        RespJ = Encoder.encode(Dict)
        Response = HttpResponse(RespJ)
        Response['Content-Type'] = 'application/json'
        return Response
    else:
        Dict = {"status": False, "description": _("A mistake has been occured during removing try one more")}
        RespJ = Encoder.encode(Dict)
        Response = HttpResponse(RespJ)
        Response['Content-Type'] = 'application/json'
        return Response


def __inner_remove_order(Order, User):
    Order2Remove = OrdersMem.objects.get(user=User, id=int(Order), status="processing")
    #if not Order2Remove.verify(str(User)) :
    #    return False

    Market = TradePairs.objects.get(id=Order2Remove.trade_pair)

    Order2Remove.status = "canceled"
    Order2Remove.save()
    Title = Market.url_title

    LOCK = "trades" + Title
    TradeLock = my_lock(LOCK)

    #try:
    Account = get_account(user_id=User, currency_id=Order2Remove.currency1)
    
    cache = caching()
    canceled_orders2deals(Order2Remove)

    trans = add_trans2(Account,
                       -1*Order2Remove.sum1,
                       Order2Remove.currency1,
                       Order2Remove,
                       "order_cancel")
                       
    put2queue(('order_cancel', trans, Market, Order2Remove))
               
    Order2Remove.archive()
    Order2Remove.delete()
    
    cache.delete_many(["buy_list_" + Title,
                       "sell_list_" + Title,
                       "balance_" + str(User),
                       'client_orders_' + str(User) + "_" + Title])

                        
    my_release(TradeLock)
    return True
    #except:

        #my_release(TradeLock)
        #return False


@json_auth_required
def sell(Req, Trade_pair):
    FreqKey = "orders" + str(Req.user)
    Start = time.time()
    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false, "description":"frequancy limit"}')
        Response['Content-Type'] = 'application/json'
        return Response

    getcontext().prec = settings.TRANS_PREC

    try:
        Count = Req.REQUEST.get("count")
        Price = Req.REQUEST.get("price")
        Count = Decimal(Count.replace(",", ".").strip())
        Price = Decimal(Price.replace(",", ".").strip())
        Count = to_prec(Count, settings.TRANS_PREC)
        Price = to_prec(Price, settings.TRANS_PREC)

    except:
        Response = HttpResponse(process_mistake(Req, "invalid_params"))
        Response['Content-Type'] = 'application/json'
        return Response

    if Price <= 0:
        Response = HttpResponse(process_mistake(Req, "SumLess0"))
        Response['Content-Type'] = 'application/json'
        return Response

    if Count <= 0:
        Response = HttpResponse(process_mistake(Req, "CountLess0"))
        Response['Content-Type'] = 'application/json'
        return Response

    TradePair = TradePairs.objects.get(url_title=Trade_pair)
    LOCK = "trades" + TradePair.url_title

    if TradePair.min_trade_base > Count:
        Response = HttpResponse(process_mistake(Req, "MinCount"))
        Response['Content-Type'] = 'application/json'

        return Response

    Custom = "0.0005"  # Req.session["deal_comission"]
    Comission = Decimal(Custom)

    CurrencyOnS = Req.REQUEST.get("currency")
    CurrencyBaseS = Req.REQUEST.get("currency1")
    Amnt1 = Count
    Amnt2 = Count * Price
    CurrencyBase = Currency.objects.get(title=CurrencyBaseS)
    CurrencyOn = Currency.objects.get(title=CurrencyOnS)
    TradeLock = my_lock(LOCK)
    order = OrdersMem(user=Req.user,
                      currency1=CurrencyOn.id,
                      sum1_history=Amnt1,
                      price=Price,
                      pub_date = datetime.now(),
                      sum1=Decimal("0.0"),
                      trade_pair=TradePair.id,
                      currency2 = CurrencyBase.id,
                      comission=Comission,
                      status="created",
                      type_deal = "sell")

    order.save()
    i = order.id
    backend = TornadoServer.get_instance()
    
    try:
        FromAccount = get_account(user_id=Req.user, currency_id=CurrencyOn.id)
        
        system_notify_async(deposit_funds(order, CurrencyOn), Req.user)
        
        trans_deposit = add_trans2(FromAccount, Amnt1, CurrencyOn.id, order, "deposit")
        put2queue(('deposit', trans_deposit, TradePair, order))
        
        order = trans_deposit.order
        order.status='processing'
        order.save()
        
        ResAuto = make_auto_trade(order, TradePair, order.price, CurrencyOn, Amnt1, CurrencyBase)
        # adding locks
        my_release(TradeLock)
        logger_application.info("reees auto")
        logger_application.info(ResAuto)
        resp_body = process_auto(ResAuto, TradePair)
        
        Response = HttpResponse(resp_body)
        Response['Content-Type'] = 'application/json'
        End = time.time()
        measure = OrderTimer(order=i, time_work=str(End - Start), error="")
        measure.save()
      
        return Response
    except Exception  as e :
        logger_application.critical(traceback.format_exc())
        order.status = "canceled"
        order.save()
        Status = "unrecognized"
        my_release(TradeLock)
        Response = HttpResponse(process_mistake(Req, Status))
        Response['Content-Type'] = 'application/json'
        End = time.time()
        tb = traceback.format_exc()
        measure = OrderTimer(order=i, time_work=str(End - Start), error=tb)
        measure.save()
        
        return Response


@json_auth_required
def buy(Req, Trade_pair):
    FreqKey = "orders" + str(Req.user)
    Start = time.time()
    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false, "description":"frequancy limit"}')
        Response['Content-Type'] = 'application/json'
        return Response

    getcontext().prec = settings.TRANS_PREC
    try:
        Count = Req.REQUEST.get("count")
        Price = Req.REQUEST.get("price")
        Count = Decimal(Count.replace(",", ".").strip())
        Price = Decimal(Price.replace(",", ".").strip())
        Count = to_prec(Count, settings.TRANS_PREC)
        Price = to_prec(Price, settings.TRANS_PREC)

    except:
        logger_application.error(traceback.format_exc())
        Response = HttpResponse(process_mistake(Req, "invalid_params"))
        Response['Content-Type'] = 'application/json'
        return Response

    if Price <= 0:
        Response = HttpResponse(process_mistake(Req, "SumLess0"))
        Response['Content-Type'] = 'application/json'
        return Response

    if Count <= 0:
        Response = HttpResponse(process_mistake(Req, "CountLess0"))
        Response['Content-Type'] = 'application/json'
        return Response

    TradePair = TradePairs.objects.get(url_title=Trade_pair)
    LOCK = "trades" + TradePair.url_title

    if TradePair.min_trade_base > Count:
        Response = HttpResponse(process_mistake(Req, "MinCount"))
        Response['Content-Type'] = 'application/json'
        return Response

    Custom = "0.0005"  # Req.session["deal_comission"]
    Comission = Decimal(Custom)

    CurrencyOnS = Req.REQUEST.get("currency")
    CurrencyBaseS = Req.REQUEST.get("currency1")

    Amnt1 = Price * Count
    Amnt2 = Count

    CurrencyBase = Currency.objects.get(title=CurrencyBaseS)
    CurrencyOn = Currency.objects.get(title=CurrencyOnS)

    TradeLock = my_lock(LOCK)
    order = OrdersMem(user=Req.user,
                      currency1=CurrencyBase.id,
                      currency2=CurrencyOn.id,
                      sum1_history=Amnt1,
                      price=Price,
                      pub_date=datetime.now(),
                      sum1=Decimal("0.0"),
                      trade_pair=TradePair.id,
                      comission=Comission,
                      status="created",
                      type_deal = "buy"
                      )
    order.save()
    i = order.id
    try:
        FromAccount = get_account(user_id=Req.user, currency_id=CurrencyBase.id)
        system_notify_async(deposit_funds(order, CurrencyBase), Req.user)
        # TODO Order to Encrypted object
        trans_deposit = add_trans2(FromAccount, Amnt1, CurrencyBase.id, order, "deposit")
        put2queue(('deposit', trans_deposit, TradePair, order))
        order = trans_deposit.order
        order.status = "processing"
        order.save()
        ResAuto = make_auto_trade(order, TradePair, order.price, CurrencyBase, Amnt1, CurrencyOn)
        Response = HttpResponse(process_auto(ResAuto, TradePair))
        my_release(TradeLock)
        Response['Content-Type'] = 'application/json'
        End = time.time()
        measure = OrderTimer(order=i, time_work=str(End - Start), error="")
        measure.save()

        return Response
    except Exception as e:
        logger_application.info(traceback.format_exc())

        order.status = "canceled"
        order.save()
        Status = "unrecognized"
        Response = HttpResponse(process_mistake(Req, Status))
        Response['Content-Type'] = 'application/json'
        my_release(TradeLock)
        End = time.time()
        tb = traceback.format_exc()
        measure = OrderTimer(order=i, time_work=str(End - Start), error=tb)
        measure.save()
        return Response


@json_auth_required
def bid(Req, UrlTitle):
    CurrentTradePair = TradePairs.objects.get(url_title=UrlTitle)
    SumList = []
    Amount = Decimal("0")
    TempSum = Decimal('0')
    try:
        Amount = Decimal(Req.REQUEST.get("amount", None))
        Query = "SELECT * FROM main_ordersmem  WHERE  currency2=%i AND currency1=%i \
                          AND status='processing'  \
                          AND user!=%i  ORDER BY price DESC" % (
            CurrentTradePair.currency_on.id,
            CurrentTradePair.currency_from.id,
            Req.user)
        List = OrdersMem.objects.raw(Query)
        for item in List:
            if Amount > item.sum1:
                Amount -= item.sum1
                TempSum += item.sum1
                SumList.append({"sum": item.sum1, "price": item.price})
            else:
                TempSum += Amount
                SumList.append({"sum": Amount, "price": item.price})
                break
    except:
        logger_application.info(traceback.format_exc())
        Response = HttpResponse('{"status":false, "description":"amount is incorrect"}')
        Response['Content-Type'] = 'application/json'
        return Response
        # format_numbers_strong(balance_buy.balance )

    AvaragePrice = Decimal("0")
    BuySum = Decimal("0")
    for item in SumList:
        BuySum += item['sum']
        AvaragePrice += ((item['sum'] / TempSum) * item['price'] )
    Dict = {"sell_sum": format_numbers_strong(BuySum),
            "price": format_numbers_strong(AvaragePrice),
            "status": True}
    RespJ = json.JSONEncoder().encode(Dict)
    return cached_json_object(RespJ)


@json_auth_required
def ask(Req, UrlTitle):
    CurrentTradePair = TradePairs.objects.get(url_title=UrlTitle)
    SumList = []
    Amount = Decimal("0")
    TempSum = Decimal('0')
    try:
        Amount = Decimal(Req.REQUEST.get("amount", None))
        Query = "SELECT * FROM main_ordersmem  WHERE  currency1=%i AND currency2=%i \
                          AND status='processing'  \
                          AND user!=%i  ORDER BY price DESC" % (
            CurrentTradePair.currency_on.id,
            CurrentTradePair.currency_from.id,
            Req.user)
        List = OrdersMem.objects.raw(Query)
        for item in List:
            if Amount > item.sum1:
                Amount -= item.sum1
                TempSum += item.sum1
                SumList.append({"sum": item.sum1, "price": item.price})
            else:
                TempSum += Amount
                SumList.append({"sum": Amount, "price": item.price})
                break
    except:
        logger_application.info(traceback.format_exc())
        Response = HttpResponse('{"status":false, "description":"amount is incorrect"}')
        Response['Content-Type'] = 'application/json'
        return Response
        # format_numbers_strong(balance_buy.balance )

    AvaragePrice = Decimal("0")
    BuySum = Decimal("0")
    for item in SumList:
        BuySum += item['sum']
        AvaragePrice += ((item['sum'] / TempSum) * item['price'] )
    Dict = {"buy_sum": format_numbers_strong(BuySum),
            "price": format_numbers_strong(AvaragePrice),
            "status": True}
    RespJ = json.JSONEncoder().encode(Dict)
    return cached_json_object(RespJ)


@my_cache()
def buy_list(Req, Pair):
    Current = None
    try:
        Current = TradePairs.objects.get(url_title=Pair)
    except:
        logger_application.info(traceback.format_exc())
        return json_false500(Req)

    BuyList = OrdersMem.objects.filter(status="processing",
                                       currency1=Current.currency_from.id,
                                       currency2=Current.currency_on.id)
    getcontext().prec = settings.TRANS_PREC
    Currency1Title = Current.currency_from.title
    Currency2Title = Current.currency_on.title
    List1 = {}
    AccumBuySum = 0
    for item in BuyList:
        SellSum = item.sum1  ## UAH
        BuySum = item.sum1/item.price  ## LTC
        Rate = item.price
        AccumBuySum += SellSum
        if List1.has_key(Rate):
            List1[Rate][Currency1Title] = List1[Rate][Currency1Title] + SellSum
            List1[Rate][Currency2Title] = List1[Rate][Currency2Title] + BuySum
        else:
            List1[Rate] = {Currency1Title: SellSum, Currency2Title: BuySum}

    ResBuyList = []

    LL = List1.keys()
    L = []
    for i in LL:
        Temp = Decimal(i)
        List1[Temp] = List1[i]
        L.append(Temp)

    L.sort()
    L.reverse()

    Price = 0
    MaxPrice = 0
    for i in L:
        Price = format_numbers10(i)
        ResBuyList.append({"price": Price,
                           "currency_trade": format_numbers10(List1[i][Currency2Title]),
                           "currency_base": format_numbers10(List1[i][Currency1Title])})

    if len(ResBuyList):
        MaxPrice = ResBuyList[0]["price"]
    Dict = {"orders_sum": format_numbers10(AccumBuySum), "list": ResBuyList,
            "max_price": MaxPrice, "min_price": Price}
    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


@json_auth_required
def order_status(Req, Id):
    Dict = {}
    try:
        order = Orders.objects.get(id=int(Id), user=Req.user)
        Dict["pub_date"] = str(order.pub_date)
        Dict["sum1"] = str(order.sum1)
        Dict["id"] = str(Id)
        Dict["sum2"] = str(order.sum2)
        Dict["sum1_history"] = str(order.sum1_history)
        Dict["sum2_history"] = str(order.sum2_history)
        Dict["currency1"] = order.currency1.title
        Dict["currency2"] = order.currency1.title
        Dict["status"] = order.status
    except Orders.DoesNotExist:
        logger_application.error(traceback.format_exc())
        return status_false()
    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    return Response


@my_cache()
def balance(Req, User_id):
    List = []
    Dict = {}
    for i in Accounts.objects.filter(user_id=User_id):
        acc = get_account(user_id=User_id, currency_id=i.currency.id)
        List.append({"balance": format_numbers10(acc.get_balance), "currency": i.currency.title})

    User = Req.user
    Dict["notify_count"] = Msg.objects.filter(user_to=User,
                                              user_from_id=1,
                                              user_hide_to="false",
                                              user_seen_to="false").count()
    Dict["msg_count"] = Msg.objects.filter(user_to=User,
                                           user_hide_to="false",
                                           user_seen_to="false").exclude(user_from_id=1).count()
    try:
        online = OnlineUsers(user_id=Req.user)
        online.save()
    except:
        online = OnlineUsers.objects.get(user_id=Req.user)
        online.pub_date =  datetime.now()
        online.save()

    if Req.session.has_key('use_f2a'):
        Dict["use_f2a"] = Req.session['use_f2a']
    else:
        Dict["use_f2a"] = False

    Dict["accounts"] = List
    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


@json_auth_required
def user_balance(Req):
    return balance(Req, Req.user)

    # Dict["accounts"] = []
    # Response =  HttpResponse( json.JSONEncoder().encode(Dict) )
    # Response['Content-Type'] = 'application/json'
    # return Response


@my_cache()
def sell_list(Req, Pair):
    Current = None
    try:
        Current = TradePairs.objects.get(url_title=Pair)
    except:
        return json_false500(Req)

    SellList = OrdersMem.objects.filter(status="processing",
                                        currency1=Current.currency_on.id,
                                        currency2=Current.currency_from.id)
    getcontext().prec = 8
    Currency1Title = Current.currency_from.title
    Currency2Title = Current.currency_on.title
    AccumSellSum = 0
    GroupSellDict = {}
    for item in SellList:
        SellSum = item.sum1  ##LTC
        BuySum = item.sum1 * item.price  ## UAH
        Rate = item.price
        AccumSellSum += SellSum
        if GroupSellDict.has_key(Rate):
            GroupSellDict[Rate][Currency2Title] = GroupSellDict[Rate][Currency2Title] + SellSum
            GroupSellDict[Rate][Currency1Title] = GroupSellDict[Rate][Currency1Title] + BuySum
        else:
            GroupSellDict[Rate] = {Currency2Title: SellSum, Currency1Title: BuySum}

    ResSellList = []
    LL = GroupSellDict.keys()
    L = []
    for i in LL:
        Temp = Decimal(i)
        GroupSellDict[Temp] = GroupSellDict[i]
        L.append(Temp)

    L.sort()
    Price = 0
    MinPrice = 0
    for i in L:
        Price = format_numbers10(i)
        ResSellList.append({"price": Price,
                            "currency_trade": format_numbers10(GroupSellDict[i][Currency2Title]),
                            "currency_base": format_numbers10(GroupSellDict[i][Currency1Title])})

    if len(ResSellList):
        MinPrice = ResSellList[0]["price"]

    Dict = {"orders_sum": format_numbers10(AccumSellSum),
            "list": ResSellList,
            "min_price": MinPrice,
            "max_price": Price}
    RespJ = json.JSONEncoder().encode(Dict)

    return RespJ


@my_cache()
def last_price(Req, Pair):
    Current = None
    try:
        Current = TradePairs.objects.get(url_title=Pair)
    except:
        return json_false500(Req)
    Dict = None
    try:
        deal = DealsMemory.objects.filter(trade_pair=Current.id).latest("id")
        Dict = {"price": format_numbers4(deal.price), "price_10": format_numbers10(deal.price)}
    except:
        Dict = {"price": "0", "price_10": "0.000000000"}

    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


### TODO stat
@my_cache()
def day_stat(Req, Pair):
    Current = TradePairs.objects.get(url_title=Pair)
    ##last value 17520
    cursor = connection.cursor()
    Q = cursor.execute("SELECT 	  sum(VolumeTrade) as VolumeTrade, \
                                  sum(VolumeBase) as VolumeBase,\
                                  max(Max) as Max,\
                                  min(Min) as Min \
                                  FROM main_stockstat WHERE  main_stockstat.Stock_id=%i \
                                  ORDER BY id DESC LIMIT  17520 " % Current.id)

    List = dictfetchall(cursor, Q)
    row = List[0]
    for i in row:
        if not row[i]:
            row[i] = format_numbers4(Decimal("0"))
        else:
            row[i] = format_numbers4(Decimal(row[i]))

    Dict = {"volume_base": row['VolumeBase'],
            "volume_trade": row['VolumeTrade'],
            "min": row['Min'],
            "max": row['Max'],
    }

    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


@my_cache()
def high_japan_stat(Req, Pair):
    Current = TradePairs.objects.get(url_title=Pair)
    # last value 17520
    List = StockStat.objects.raw("SELECT * FROM main_stockstat WHERE  main_stockstat.Stock_id=%i \
                                  ORDER BY id DESC LIMIT  17520 " % Current.id)
    ListJson = []
    VolumeBase = 0
    VolumeTrade = 0
    i = 0
    for item in List:
        StartDate = item.start_date
        if i < 48:
            VolumeTrade = VolumeTrade + item.VolumeTrade
            VolumeBase = VolumeBase + item.VolumeBase
        i += 1
        Key = calendar.timegm(StartDate.utctimetuple())
        ListJson.append([int(Key) * 1000, float(item.Start), float(item.Max), float(item.Min), float(item.End),
                         float(item.VolumeTrade)])

    OnlineUsersCount = OnlineUsers.objects.count()
    ListJson.reverse()

    Dict = {"trades": ListJson,
            "online": OnlineUsersCount,
            "volume_base": str(VolumeBase),
            "volume_trade": str(VolumeTrade)}

    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


@my_cache()
def japan_stat(Req, Pair):
    Current = None
    try:
        Current = TradePairs.objects.get(url_title=Pair)
    except:
        return json_false500(Req)

    List = StockStat.objects.raw("SELECT * FROM main_stockstat WHERE  main_stockstat.Stock_id=%i \
                                  ORDER BY id DESC LIMIT 48 " % Current.id)
    ListJson = []
    VolumeBase = 0
    VolumeTrade = 0
    for item in List:
        StartDate = item.start_date
        VolumeTrade = VolumeTrade + item.VolumeTrade
        VolumeBase = VolumeBase + item.VolumeBase
        Key = "%i:%i" % (StartDate.hour, StartDate.minute)
        ListJson.append(
            [Key, float(item.Start), float(item.Max), float(item.Min), float(item.End), float(item.VolumeTrade)])

    OnlineUsersCount = OnlineUsers.objects.count()
    ListJson.reverse()

    Dict = {"trades": ListJson,
            "online": OnlineUsersCount,
            "volume_base": str(VolumeBase),
            "volume_trade": str(VolumeTrade)}

    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


##TODO add date filters
@my_cache(30)
def deal_list(Req, Pair):
    ResList = common_deal_list(Pair)
    JsonP = json.JSONEncoder().encode(ResList)
    return JsonP


def common_deal_list(Pair, User_id=None):
    Current = None
    try:
        Current = TradePairs.objects.get(url_title=Pair)
    except:
        return json_false500(Req)

    ldeals = None
    startdate =  datetime.now()
    # TODO adding paging for client orders
    if User_id is None:
        enddate = startdate - timedelta(days=30)
        ldeals = DealsMemory.objects.filter(trade_pair=Current.id, pub_date__gte=enddate).order_by('-pub_date')[:200]
    else:
        enddate = startdate - timedelta(days=365)
        ldeals = DealsMemory.objects.filter(trade_pair=Current.id, user_id=User_id, pub_date__gte=enddate ).order_by('-pub_date')[:200]

    ResList = []
    for item in ldeals:
        new_item = {}
        rate = item.price
        new_item['pub_date'] = (item.pub_date - datetime(1970,1,1)).total_seconds()  # formats.date_format(item.pub_date, "DATETIME_FORMAT")
        new_item["type"] = item.type_deal
        new_item["user"] = item.user
        new_item["price"] = format_numbers10(rate)
        new_item["amnt_base"] = format_numbers10(item.amnt_base)
        new_item["amnt_trade"] = format_numbers10(item.amnt_trade)
        ResList.append(new_item)

    return ResList


@json_auth_required
def my_closed_orders(Req, Pair):
    ResList = common_deal_list(Pair, Req.user)
    Response = HttpResponse(json.JSONEncoder().encode(ResList))
    Response['Content-Type'] = 'application/json'
    return Response


@my_cache()
def client_orders(Req, User_id, Title):
    Dict = {}

    Current = None
    try:
        Current = TradePairs.objects.get(url_title=Title)
    except:
        return json_false500(Req)



    Dict["auth"] = True
    MyOrders = OrdersMem.objects.filter(user = User_id,
                                        trade_pair = Current.id,
                                        status='processing')

    MyOrdersList = []
    c = getcontext()
    c.prec = settings.TRANS_PREC

    for i in MyOrders:
        MyOrdersDict = {}
        MyOrdersDict["pub_date"] = (i.pub_date-datetime(1970,1,1)).total_seconds()  
        # formats.date_format(i.pub_date, "DATETIME_FORMAT")
        MyOrdersDict["id"] = i.id
        MyOrdersDict["sum1"] = str(i.sum1)

        if i.currency1 == Current.currency_on.id:
            MyOrdersDict["type"] = "sell"
            MyOrdersDict["price"] = format_numbers10(i.price)
            MyOrdersDict["amnt_trade"] = format_numbers10(i.sum1)
            MyOrdersDict["amnt_base"] = format_numbers10(i.sum1*i.price)
        else:
            MyOrdersDict["type"] = "buy"
            MyOrdersDict["price"] = format_numbers10(i.price)
            MyOrdersDict["amnt_base"] = format_numbers10(i.sum1)
            MyOrdersDict["amnt_trade"] = format_numbers10(i.sum1/i.price)
        MyOrdersList.append(MyOrdersDict)

    balance_sell = get_account(user_id=User_id, currency=Current.currency_on)
    balance_buy = get_account(user_id=User_id, currency=Current.currency_from)
    Dict["balance_buy"] = format_numbers_strong(balance_buy.get_balance)
    Dict["balance_sell"] = format_numbers_strong(balance_sell.get_balance)
    Dict["your_open_orders"] = MyOrdersList
    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ


@json_auth_required
def my_orders(Req, Title):
    return client_orders(Req, Req.user, Title)
        
        




     



