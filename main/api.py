# -*- coding: utf-8 -*-

# Create your views here.
from django.template import Context, loader
from django.http import  HttpResponse 
from crypton import settings
from django.utils.translation import ugettext as _
from django.utils import formats

from django.db import connection
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from main.models import UserCustomSettings, VolatileConsts, Accounts, TradePairs, Orders, Trans, Currency, Msg, add_trans, TransError, StockStat, OnlineUsers
from django.views.decorators.cache import cache_page
from main.http_common import caching, cached_json_object, my_cache, status_false, json_auth_required, auth_required, check_api_sign
from main.http_common import format_numbers10, format_numbers_strong, format_numbers, format_numbers4, json_false500, json_true
import logging
logger = logging.getLogger(__name__)
from main.models import dictfetchall, to_prec, OrderTimer
from  main.msgs  import system_notify
import json
import decimal
from decimal import Decimal, getcontext
import datetime
import calendar
import time
from datetime import timedelta
from main.my_cache_key import my_lock, my_release, LockBusyException, check_freq



                
def get_account(user, currency):
       return Accounts.objects.get(user = user, currency = currency) 

### account buyer, sum to buy, item - order seller, Order - order buyer
def create_order(User, Amnt1, Amnt2, Currency1, Currency2, TradePair, Status = "created"  ):
        if TradePair.currency_on.id == Currency1.id:
              transit1 = TradePair.transit_on
              transit2 = TradePair.transit_from
        else :
              transit2 = TradePair.transit_on
              transit1 = TradePair.transit_from  
        
        
        order = Orders(user = User,
                                currency1 = Currency1,
                                currency2 = Currency2, 
                                sum1_history = Amnt1,
                                sum2_history = Amnt2,
                                sum1 = Amnt1, 
                                sum2 = Amnt2,
                                transit_1 = transit1,
                                transit_2 = transit2,
                                trade_pair = TradePair,
                                status = Status
                                )
        order.save()
        return order
                         
def deposit_funds(Order):        
        return _("Deposit funds  %(sum)s %(currency)s according with order #%(order_id)i " % {
                                                                              'sum' :     Order.sum1_history,
                                                                              'currency': Order.currency1.title, 
                                                                              'order_id': Order.id } )

                         
def order_finish(Order):
        return _("You order #%(order_id)i is fully completed" % { 'order_id': Order.id } )

def order_description_buy(Sum1, Sum2, Order, BackOrder,  TradePair):
        Price = BackOrder.price
        if Order.currency2 == TradePair.currency_on:
               return _("Buying %(sum).8f %(currency)s according with order  #%(order_id)i, price %(price).8f  " % 
                                                                                         {'sum':Sum2, 
                                                                                          'currency': str(TradePair.currency_on), 
                                                                                          'order_id': Order.id,
                                                                                          'price':    Price })
        else: 
               return _("Selling  %(sum).8f %(currency)s according with order #%(order_id)i, price %(price).8f  " % {
                                                                                             'sum': Sum1,
                                                                                             'currency' : str(TradePair.currency_on),
                                                                                             'order_id' : Order.id,
                                                                                             'price': Price } )
       
def order_return_unused( Order, AccumSumToSell ):
        return _("Return %(sum).8f %(currency)s unused funds according with order #%(order_id)i  " %   
                 {
                'sum':AccumSumToSell,
                'currency' : str(Order.currency1),
                'order_id': Order.id 
                 }
                 )           


def order_description_sell(Sum1, Sum2, Order,  TradePair):
         Price  = Order.price
         if Order.currency2 == TradePair.currency_on:
               

               return _("Buying %(sum).8f %(currency)s according with order  #%(order_id)i, price %(price).8f  " % {
                                                                                           'sum' :Sum2, 
                                                                                           'currency': str(TradePair.currency_on), 
                                                                                           'order_id': Order.id,
                                                                                           'price': Price })
         else:
                          
               return _("Selling  %(sum).8f %(currency)s according with order #%(order_id)i, price %(price).8f  " % 
                                                                                            {'sum':Sum1,
                                                                                             'currency': str(TradePair.currency_on),
                                                                                             'order_id':Order.id,
                                                                                             'price':Price})

#AccumSum2Buy, AccumSumToSell
def process_order(AccountBuyer, ComisBuy, AccumSum, AccumSumToSell,  item, Order, TradePair, ComisSell ):
        ##TODO move to settings for every user 
        ComisPercentSeller =  item.comission
        ComisPercentBuyer =  Order.comission

        if item.sum1 > AccumSum :
            ## a danger of low overflow    
            Diff =  AccumSum / item.sum1
            TransSum   = item.sum2*Diff 
            #TransSum = AccumSumToSell
            AccountSeller = get_account(item.user, item.currency2)
            add_trans(item.transit_2,
                      TransSum,
                      item.currency2,
                      AccountSeller,
                      item,
                      "deal",
                      Out_order_id = Order.id
                      )          
            
            add_trans(AccountSeller ,
                      TransSum*ComisPercentSeller,
                      item.currency2,
                      ComisSell,
                      item,
                      "comission",
                      Out_order_id = Order.id
                      )
            
                
            add_trans(item.transit_1,
                      AccumSum,
                      item.currency1,
                      AccountBuyer,
                      item,
                      "deal",
                      Out_order_id = Order.id
                      )
           
            add_trans(AccountBuyer,
                      AccumSum*ComisPercentBuyer,
                      item.currency1,
                      ComisBuy,
                      Order,
                      "comission",
                      Out_order_id = Order.id)           
            
            ##comission
            item.sum1  = item.sum1 - AccumSum
            item.sum2  = item.sum2 - TransSum
            item.save()  
            try:
                system_notify(order_description_sell(AccumSum, TransSum, item, TradePair), AccountSeller.user)  
                system_notify(order_description_buy(TransSum, AccumSum,  Order, item,  TradePair), AccountBuyer.user)
            except :
                pass

            return (0, AccumSumToSell - TransSum )
    
        if item.sum1 <= AccumSum :            
                
            TransSum   = item.sum2  
            NotifySum = item.sum1    
            AccountSeller = get_account(item.user, item.currency2)
            add_trans(item.transit_2,
                      TransSum,
                      item.currency2,
                      AccountSeller,
                      item,
                      "deal",
                      Out_order_id = Order.id)
            
            
            add_trans(AccountSeller ,
                      TransSum*ComisPercentSeller,
                      item.currency2,
                      ComisSell,
                      item,
                      "comission",
                      Out_order_id = Order.id)  
            

            add_trans(item.transit_1,
                      NotifySum,
                      item.currency1,
                      AccountBuyer,
                      item,
                     "deal",
                     Out_order_id = Order.id)
            
            add_trans(AccountBuyer,
                      NotifySum*ComisPercentBuyer,
                      item.currency1,
                      ComisBuy,
                      Order,
                     "comission",
                     Out_order_id = Order.id)
          

            ##comission            
            item.status = "processed"
            item.sum1  = 0
            item.sum2  = 0
            item.save()  
            
            try :
                system_notify(order_description_sell(NotifySum, TransSum, item, TradePair), AccountSeller.user)  
                system_notify(order_description_buy(TransSum,  NotifySum,  Order, item, TradePair), AccountBuyer.user)            
                system_notify(order_finish(item), AccountSeller.user)  
            except :
                pass
                     
            return  (AccumSum - NotifySum, AccumSumToSell - TransSum )                                 



                
def auth(Req):   
    Nonce = Req.REQUEST.get("nonce", None)
    if Nonce is None :
        return json_false500(Req)
    
    (Sign, PublicKey) = (None, None)
    Sign = Req.META.get('HTTP_API_SIGN', None)
 
    if Sign is None:
        return json_false500(Req, {"description":"invalid_params", "key": "api_sign"} )
        
    
    PublicKey = Req.META.get('HTTP_PUBLIC_KEY', None)
    if PublicKey is None:
        return json_false500(Req, {"description":"invalid_params","key": "public_key"} )

    try :
        Req.user = check_api_sign(PublicKey, Sign, Req.body )
        Cache = caching()
        Cache.set("nonce_" + PublicKey, int(Nonce), 50000)    
        Nonce = Cache.get("nonce_" + PublicKey)
        return json_true(Req, {"nonce": Nonce,"public_key": PublicKey})
    except:
        return json_false500(Req,{"description":"auth_faild"})
                    
                
def make_auto_trade(Order, TradePair, Price, Currency1, Sum1, Currency2, Sum2):
        
    List = None    
    ##if we sell
    if    int(TradePair.currency_on.id) ==  int(Currency1.id):
        Query = "SELECT * FROM main_orders  WHERE  currency1_id=%i AND currency2_id=%i \
                          AND status='processing' AND price >= %s  \
                          AND  user_id!=%i  ORDER BY price DESC" % (
                                                                    Currency2.id, 
                                                                    Currency1.id,
                                                                    format_numbers_strong( Price ), Order.user.id)    
    else :
        Query = "SELECT * FROM main_orders WHERE  currency1_id=%i AND currency2_id=%i \
                          AND status='processing' AND price <= %s \
                          AND user_id!=%i ORDER BY price " % (Currency2.id,
                                                              Currency1.id,
                                                              format_numbers_strong( Price ), Order.user.id )     
    List = Orders.objects.raw(Query)
    ##work on first case
    CommissionSell = Accounts.objects.get(user_id = settings.COMISSION_USER, currency = Currency1)
    ComnissionBuy = Accounts.objects.get(user_id = settings.COMISSION_USER, currency = Currency2)
    AccumSumToSell = Sum1
    AccumSum2Buy = Sum2
    AccountBuyer  = get_account(Order.user, Currency2)
    UserDeals = [Order.user.id]
    for item in List:
            (AccumSum2Buy, AccumSumToSell ) =  process_order(AccountBuyer, ComnissionBuy,  AccumSum2Buy,
                                                             AccumSumToSell,  item, Order,
                                      TradePair, CommissionSell )
            UserDeals.append([item.user_id])
            if AccumSum2Buy>0.00000001 :
                continue
            else :
                break    

            
    ResultSum  = finish_create_order(TradePair, AccumSum2Buy, AccumSumToSell, Order)    
    Order.sum1 = AccumSumToSell
    
    if  ResultSum>0.00000001:  
        Order.sum2 = ResultSum
    else:
        Order.sum2 = 0
        Order.status = "processed"
    
    ##if order has rest of funds return all to account
    if AccumSumToSell>0 and Order.sum2 == 0 and  Order.status == "processed":
            return_rest2acc(Order, AccumSumToSell)
            Order.sum1 = 0
  
        
    Order.save()
    return {"start_sum":Sum2 , "last_sum": ResultSum, "users_bothered" : UserDeals }

def return_rest2acc(Order, AccumSumToSell):
           Account2Sell  = get_account(Order.user, Order.currency1)
           add_trans(Order.transit_1, 
           AccumSumToSell, 
           Order.currency1,
           Account2Sell,
           Order,
           "deal_return")
           system_notify( order_return_unused( Order, AccumSumToSell ), Order.user )  

                       

    
def finish_create_order(TradePair, SumToBuy, AccumSumToSell, Order):
          ##base currency
          if Order.currency1 == TradePair.currency_on : 
                 
                if AccumSumToSell < TradePair.min_trade_base :                        
                        system_notify(order_finish(Order), Order.user)
                        return 0
                else:
                        return SumToBuy
          else:   
                if SumToBuy < TradePair.min_trade_base :
                        system_notify(order_finish(Order), Order.user)
                        return 0
                else:
                        return SumToBuy   
                

        

def process_auto(Req,  Res, TradePair):
        Dict = None
        Encoder = json.JSONEncoder()


        if Res["start_sum"] == Res["last_sum"]:
                Dict = {"status": True, "description": _("The order has been created") }
                
        
        elif  Res["last_sum"] < TradePair.min_trade_base:
                Dict = {"status": "processed",
                        "description": _("Your order has been fully processed successfully"),
                        "start_sum_to_buy": str(Res["start_sum"]),
                        "last_sum_to_buy":  str(Res["last_sum"])
                        }      
        elif Res["start_sum"] > Res["last_sum"] :
                Dict = {"status": "processed", "description": _("Your order has been  processed partial"),
                        "start_sum_to_buy": str(Res["start_sum"]),
                        "last_sum_to_buy":  str(Res["last_sum"])
                        }
        
        DeleteKeys = []
        cache = caching()
        Type = TradePair.url_title
        for i in Res["users_bothered"]:
                CachedKey1 = 'client_orders_' + str(i) + "_" + Type
                CachedKey2 = 'balance_' + str(i)
                DeleteKeys.append(CachedKey1)
                DeleteKeys.append(CachedKey2)
        #deal_list_btc_uah
        DeleteKeys.append("deal_list_" +  Type)
        DeleteKeys.append("sell_list_" +  Type)
        DeleteKeys.append("buy_list_" +   Type)

        cache.delete_many(DeleteKeys)
        
        return Encoder.encode(Dict)

def process_mistake(Req, Mistake):
        Dict = None
        Encoder = json.JSONEncoder()


        if Mistake == 'incifition_funds' :
                Dict = {"status": Mistake, "description": u"У вас недостаточно средст для этой операции, пополните ваш счет во вкладке <a href='/finance'> \"финансы\" </a>   " } 
        elif Mistake == "MinCount":
                Dict = {"status": Mistake, "description": _("Count of deal is too small") } 
        elif Mistake == "invalid_params":
                Dict = {"status": Mistake, "description": _("Invalid params") }
        else:
                Dict = {"status": Mistake, "description":  _("Some mistake has been occured, try later, or call support")} 
        return Encoder.encode(Dict)


@my_cache
def market_prices(Req):
       
        
        Dict = None
        Encoder = json.JSONEncoder()
        prices = []
        for item in TradePairs.objects.filter(status = "processing").order_by("ordering"):
          TopName = item.url_title + "_top_price"      
          Price = VolatileConsts.objects.get(Name = TopName)        
          prices.append({"type":TopName, "price":Price.Value})
        RespJ  = Encoder.encode({"prices": prices})
        return RespJ
 
 
        
@json_auth_required
def remove_order(Req, Order):
     Encoder = json.JSONEncoder()
        
     FreqKey = "orders" + str(Req.user.id)
     if not check_freq(FreqKey, 3) :
        Response =   HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response        


     if not Req.user.is_authenticated():
                Dict = {"status":"auth_error","description":_("You must login")};
                RespJ  = Encoder.encode(Dict)
                Response =   HttpResponse(RespJ)
                Response['Content-Type'] = 'application/json'
                return Response
     else :
                if __inner_remove_order(Order, Req.user):
                      Dict = {"status":True };
                      RespJ  = Encoder.encode(Dict)
                      Response =   HttpResponse(RespJ)
                      Response['Content-Type'] = 'application/json'
                      return Response
                else :
                      Dict = {"status":False, "description": _("A mistake has been occured during removing try one more") };
                      RespJ  = Encoder.encode(Dict)
                      Response =   HttpResponse(RespJ)
                      Response['Content-Type'] = 'application/json'
                      return Response    
                  

 
def __inner_remove_order(Order, User):
    Order2Remove  = Orders.objects.get(user = User, id = int(Order), status="processing" )
    Title =  Order2Remove.trade_pair.url_title
    LOCK = "trades" + Title
    TradeLock = my_lock(LOCK)

    try :
       Order2Remove.status = "canceled"
       Order2Remove.save()
       Account = Accounts.objects.get(user = User, currency = Order2Remove.currency1)
       add_trans(Order2Remove.transit_1, 
                 Order2Remove.sum1, 
                 Order2Remove.currency1,
                 Account,
                 Order2Remove,
                 "order_cancel")  
       cache = caching()
       
       
       cache.delete_many(["buy_list_" + Title, 
                          "sell_list_" + Title,
                          "balance_"  + str(User.id),
                          'client_orders_' + str(User.id) + "_" + Title])
       
       my_release(TradeLock)
       return True          
    except:

       my_release(TradeLock)
       return False
    
@json_auth_required
def sell(Req, Trade_pair):  
		 
                FreqKey = "orders" + str(Req.user.id)
                Start = time.time()
                if not check_freq(FreqKey, 3) :
                    Response =   HttpResponse('{"status":false,"description":false}')
                    Response['Content-Type'] = 'application/json'
                    return Response
                
                getcontext().prec = settings.TRANS_PREC
                
                try :
                        Count = Req.REQUEST.get("count")
                        Price = Req.REQUEST.get("price")
                        Count  = Decimal( Count.replace(",",".").strip() )
                        Price  = Decimal( Price.replace(",",".").strip() ) 
                        Count = to_prec(Count, settings.TRANS_PREC )                      
                        Price = to_prec(Price, settings.TRANS_PREC )                      
                        
                except:
                        Response =   HttpResponse(process_mistake(Req, "invalid_params"))
                        Response['Content-Type'] = 'application/json'
                        return Response
                
                if Price <= 0:
                        Response =   HttpResponse(process_mistake(Req, "SumLess0"))
                        Response['Content-Type'] = 'application/json'
                        return Response
                        
                if Count<=0:
                        Response =   HttpResponse(process_mistake(Req, "CountLess0"))
                        Response['Content-Type'] = 'application/json'
                        return Response
                
                TradePair =  TradePairs.objects.get(url_title = Trade_pair) 
                LOCK = "trades" + TradePair.url_title
                
                if TradePair.min_trade_base > Count:
                        Response =   HttpResponse(process_mistake(Req, "MinCount"))
                        Response['Content-Type'] = 'application/json'
                        
                        return Response
                        
                Custom = "0.0005" #Req.session["deal_comission"] 
                Comission = Decimal(Custom)
                
                CurrencyOnS = Req.REQUEST.get("currency") 
                CurrencyBaseS  = Req.REQUEST.get("currency1")
                Amnt1 = Count
                Amnt2 = Count * Price
                
                CurrencyBase = Currency.objects.get(title =  CurrencyBaseS )
                CurrencyOn = Currency.objects.get(title =  CurrencyOnS )
                TradeLock = my_lock(LOCK)
                order = Orders( user = Req.user,
                                currency1 = CurrencyOn,
                                currency2 = CurrencyBase, 
                                sum1_history = Amnt1,
                                sum2_history = Amnt2,
                                price = Price,
                                sum1 = Amnt1, 
                                sum2 = Amnt2,
                                transit_1 = TradePair.transit_on,
                                transit_2 = TradePair.transit_from,
                                trade_pair = TradePair,
                                comission = Comission
                                )
                order.save()

                try: 
                        FromAccount = Accounts.objects.get(user = Req.user, currency = CurrencyOn)
                        add_trans(FromAccount, Amnt1, CurrencyOn, TradePair.transit_on, order, "deposit")                      
                        order.status = "processing"
                        order.save()
                        system_notify(deposit_funds(order), Req.user)  
                        ResAuto = make_auto_trade(order, TradePair, order.price, CurrencyOn, Amnt1, CurrencyBase, Amnt2)
                        my_release(TradeLock)
                        Response = HttpResponse(process_auto(Req, ResAuto, TradePair))
                        Response['Content-Type'] = 'application/json'
                        
                        End = time.time()
                        measure = OrderTimer(order = order,time_work = str(End - Start))
                        measure.save()
                        
                        return Response 
                except TransError as e: 
                        order.status = "canceled"
                        order.save()
                        Status = e.value
                        my_release(TradeLock)
                        Response =   HttpResponse(process_mistake(Req, Status))
                        Response['Content-Type'] = 'application/json'
                        End = time.time()
                        measure = OrderTimer(order = order,time_work = str(End - Start))
                        measure.save()
                        return Response
@json_auth_required
def buy(Req, Trade_pair):
                FreqKey = "orders" + str(Req.user.id)
                Start = time.time()
                if not check_freq(FreqKey, 3):
                        Response =   HttpResponse('{"status":false}')
                        Response['Content-Type'] = 'application/json'
                        return Response
                        
                 
                getcontext().prec = settings.TRANS_PREC
                try :
                        Count = Req.REQUEST.get("count")
                        Price = Req.REQUEST.get("price")
                        Count  = Decimal( Count.replace(",",".").strip() )
                        Price  = Decimal( Price.replace(",",".").strip() ) 
                        Count = to_prec(Count, settings.TRANS_PREC )                      
                        Price = to_prec(Price, settings.TRANS_PREC )     
                        
                except:
                        Response =   HttpResponse(process_mistake(Req, "invalid_params"))
                        Response['Content-Type'] = 'application/json'
                        return Response
               
                if Price <= 0:
                        Response =   HttpResponse(process_mistake(Req, "SumLess0"))
                        Response['Content-Type'] = 'application/json'
                        return Response
                        
                if Count<=0:
                        Response =   HttpResponse(process_mistake(Req, "CountLess0"))
                        Response['Content-Type'] = 'application/json'
                        return Response                
                
                TradePair =  TradePairs.objects.get(url_title = Trade_pair) 
                LOCK = "trades" + TradePair.url_title
                
                if TradePair.min_trade_base > Count:
                        Response =   HttpResponse(process_mistake(Req, "MinCount"))
                        Response['Content-Type'] = 'application/json'
                        return Response
                        
                Custom = "0.0005"# Req.session["deal_comission"]    
                Comission = Decimal(Custom)
                
                CurrencyOnS = Req.REQUEST.get("currency") 
                CurrencyBaseS  = Req.REQUEST.get("currency1")
                
                Amnt1 = Price * Count 
                Amnt2 = Count         
                
                
                
                CurrencyBase = Currency.objects.get(title =  CurrencyBaseS )
                CurrencyOn = Currency.objects.get(title =  CurrencyOnS )
                
                TradeLock = my_lock(LOCK)
                order = Orders(user = Req.user,
                                currency1 = CurrencyBase,
                                currency2 = CurrencyOn, 
                                price = Price,
                                sum1_history = Amnt1,
                                sum2_history = Amnt2,
                                sum1 = Amnt1, 
                                sum2 = Amnt2,
                                transit_1 = TradePair.transit_from,
                                transit_2 = TradePair.transit_on,
                                trade_pair = TradePair,
                                comission = Comission
                                )
                order.save()

                try: 
                        FromAccount = Accounts.objects.get(user = Req.user, currency = CurrencyBase)
                        add_trans(FromAccount, Amnt1, CurrencyBase, TradePair.transit_from, order, "deposit")                      
                        order.status = "processing"
                        order.save()
                        system_notify(deposit_funds(order), Req.user)                  
                        
                        ResAuto = make_auto_trade(order, TradePair, order.price, CurrencyBase, Amnt1, CurrencyOn, Amnt2)
                        
                        Response = HttpResponse(process_auto(Req, ResAuto, TradePair))

                        my_release(TradeLock)
                        Response['Content-Type'] = 'application/json'
                        End = time.time()
                        measure = OrderTimer(order = order,time_work = str(End - Start))
                        measure.save()
                        
                        return Response 
                except TransError as e: 
                        order.status = "canceled"
                        order.save()
                        Status = e.value
                        Response =   HttpResponse(process_mistake(Req, Status))
                        Response['Content-Type'] = 'application/json'
                        my_release(TradeLock)
                        
                        End = time.time()
                        measure = OrderTimer(order = order,time_work = str(End - Start))
                        measure.save()
                        
                        return Response 



@json_auth_required
def bid(Req, UrlTitle):
    CurrentTradePair = TradePairs.objects.get(url_title = UrlTitle)
    SumList = []
    Amount = Decimal("0")
    TempSum = Decimal('0')
    try: 
        Amount = Decimal( Req.REQUEST.get("amount", None) )
        Query = "SELECT * FROM main_orders  WHERE  currency2_id=%i AND currency1_id=%i \
                          AND status='processing'  \
                          AND user_id!=%i  ORDER BY price DESC" % (
                                                                    CurrentTradePair.currency_on.id, 
                                                                    CurrentTradePair.currency_from.id,
                                                                    Req.user.id)
        List = Orders.objects.raw(Query)
        for item in List:
             if Amount > item.sum1 :
                  Amount -=  item.sum1
                  TempSum += item.sum1
                  SumList.append({"sum":item.sum1,"price":item.price})
             else:
                  TempSum += Amount
                  SumList.append({"sum":Amount,"price":item.price})  
                  break              
    except :
        Response =   HttpResponse('{"status":false, "description":"amount is incorrect"}')
        Response['Content-Type'] = 'application/json'
        return Response   
    #format_numbers_strong(balance_buy.balance )
    
    AvaragePrice = Decimal("0")
    BuySum  = Decimal("0")
    for item in SumList:
        BuySum += item['sum']    
        AvaragePrice += ((item['sum']/TempSum)*item['price'] )
    Dict = {"sell_sum": format_numbers_strong(BuySum),
             "price":  format_numbers_strong(AvaragePrice),
             "status":True  }
    RespJ =  json.JSONEncoder().encode(Dict)
    return cached_json_object(RespJ)


@json_auth_required
def ask(Req, UrlTitle):
    CurrentTradePair = TradePairs.objects.get(url_title = UrlTitle)
    SumList = []
    Amount = Decimal("0")
    TempSum = Decimal('0')
    try: 
        Amount = Decimal( Req.REQUEST.get("amount", None) )
        Query = "SELECT * FROM main_orders  WHERE  currency1_id=%i AND currency2_id=%i \
                          AND status='processing'  \
                          AND user_id!=%i  ORDER BY price DESC" % (
                                                                    CurrentTradePair.currency_on.id, 
                                                                    CurrentTradePair.currency_from.id,
                                                                    Req.user.id)
        List = Orders.objects.raw(Query)
        for item in List:
             if Amount > item.sum1 :
                  Amount -=  item.sum1
                  TempSum += item.sum1
                  SumList.append({"sum":item.sum1,"price":item.price})
             else:
                  TempSum += Amount
                  SumList.append({"sum":Amount,"price":item.price})  
                  break              
    except :
        Response =   HttpResponse('{"status":false, "description":"amount is incorrect"}')
        Response['Content-Type'] = 'application/json'
        return Response   
    #format_numbers_strong(balance_buy.balance )
    
    AvaragePrice = Decimal("0")
    BuySum  = Decimal("0")
    for item in SumList:
        BuySum += item['sum']    
        AvaragePrice += ((item['sum']/TempSum)*item['price'] )
    Dict = {"buy_sum": format_numbers_strong(BuySum),
            "price":  format_numbers_strong(AvaragePrice),
            "status":True  }
    RespJ =  json.JSONEncoder().encode(Dict)
    return cached_json_object(RespJ)


@my_cache
def buy_list(Req, Pair):
        Current = None
        try:
            Current = TradePairs.objects.get(url_title = Pair)
        except :
            return json_false500(Req)
        
        
        
        BuyList =  Orders.objects.filter(status = "processing",
                                        currency1 = Current.currency_from,
                                        currency2 = Current.currency_on)
        getcontext().prec = settings.TRANS_PREC
        Currency1Title = Current.currency_from.title
        Currency2Title = Current.currency_on.title
        List1 = {}
        AccumBuySum = 0
        for item in BuyList : 
                SellSum = item.sum1 ## UAH
                BuySum = item.sum2  ## LTC
                Rate = item.price
                AccumBuySum += SellSum
                if List1.has_key(Rate) :
                        List1[Rate][Currency1Title] = List1[Rate][Currency1Title] + SellSum
                        List1[Rate][Currency2Title] = List1[Rate][Currency2Title] + BuySum
                else :
                        List1[Rate] = {Currency1Title: SellSum, Currency2Title: BuySum }
        
        ResBuyList = []
        
        LL = List1.keys()
        L = []
        for i in LL:
             Temp = Decimal(i)
             List1[Temp] =  List1[i]    
             L.append( Temp )   
             
        L.sort()
        L.reverse()
        
        Price  = 0
        MaxPrice  = 0
        for i in  L :
                Price = format_numbers10(i)
                ResBuyList.append( {"price":Price, 
                                    "currency_trade": format_numbers10(List1[i][Currency2Title]),
                                    "currency_base": format_numbers10(List1[i][Currency1Title]) } )    

        if len(ResBuyList):
                MaxPrice = ResBuyList[0]["price"]
        Dict = {"orders_sum":format_numbers10(AccumBuySum), "list":ResBuyList,
                 "max_price":MaxPrice, "min_price": Price }
        RespJ =  json.JSONEncoder().encode(Dict)
        return RespJ
        


@json_auth_required
def order_status(Req, Id):
        Dict = {}
        try :
                order = Orders.objects.get(id = int(Id), user = Req.user)
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
               return status_false()
        Response =  HttpResponse( json.JSONEncoder().encode(Dict) )
        Response['Content-Type'] = 'application/json'
        return Response


@my_cache
def balance(Req, User_id):
            List = []
            Dict = {}
            for i in Accounts.objects.filter(user_id = User_id):
                List.append({"balance": format_numbers10(i.balance),"currency": i.currency.title })               
                
            User = Req.user        
            Dict["notify_count"] = Msg.objects.filter(user_to = User, 
                                                  user_from_id = 1,
                                                  user_hide_to = "false",
                                                  user_seen_to = "false" ).count()
            Dict["msg_count"] = Msg.objects.filter(user_to = User, 
                                                user_hide_to = "false",
                                                user_seen_to = "false" ).exclude(user_from_id = 1).count()
            try:
                online = OnlineUsers(user = Req.user )
                online.save()
            except :
                online = OnlineUsers.objects.get(user = Req.user )    
                online.pub_date = datetime.datetime.now()
                online.save()
            
            if Req.session.has_key('use_f2a'):
                Dict["use_f2a"]= Req.session['use_f2a'] 
            else:
                Dict["use_f2a"] = False     
            
            Dict["accounts"] = List
            RespJ = json.JSONEncoder().encode(Dict)
            return RespJ
    
@json_auth_required
def user_balance(Req):
        Dict = {}
        return balance(Req, Req.user.id)               
                
        #Dict["accounts"] = []
        #Response =  HttpResponse( json.JSONEncoder().encode(Dict) )
        #Response['Content-Type'] = 'application/json'
        #return Response

@my_cache
def sell_list(Req, Pair):              
        Current = None
        try:
            Current = TradePairs.objects.get(url_title = Pair)
        except :
            return json_false500(Req)
            
        SellList = Orders.objects.filter(status = "processing",
                                      currency1 = Current.currency_on,
                                      currency2 = Current.currency_from)
        getcontext().prec = 8
        Currency1Title = Current.currency_from.title
        Currency2Title = Current.currency_on.title
        AccumSellSum = 0
        GroupSellDict = {}
        for item in SellList :
             SellSum = item.sum1 ##LTC
             BuySum = item.sum2 ## UAH
             Rate = item.price
             AccumSellSum += SellSum
             if GroupSellDict.has_key(Rate) :
                GroupSellDict[Rate][Currency2Title] = GroupSellDict[Rate][Currency2Title] + SellSum
                GroupSellDict[Rate][Currency1Title] = GroupSellDict[Rate][Currency1Title] + BuySum
             else :
                GroupSellDict[Rate] = {Currency2Title: SellSum, Currency1Title: BuySum }
                
        ResSellList = [] 
        LL = GroupSellDict.keys()
        L = []
        for i in LL:
             Temp = Decimal(i)
             GroupSellDict[Temp] =  GroupSellDict[i]    
             L.append( Temp )   
             
        L.sort()
        
        Price  = 0
        MinPrice = 0
        for i in L:
                Price = format_numbers10(i)
                ResSellList.append( {"price":Price,
                                     "currency_trade":format_numbers10(GroupSellDict[i][Currency2Title]),
                                     "currency_base": format_numbers10(GroupSellDict[i][Currency1Title]) } )
                
        if len(ResSellList):
                MinPrice = ResSellList[0]["price"]    
    
        Dict = {"orders_sum":format_numbers10(AccumSellSum), 
                "list":ResSellList,
                "min_price": MinPrice, 
                "max_price": Price }
        RespJ = json.JSONEncoder().encode(Dict)
        
        return RespJ

        

### TODO stat

@my_cache
def high_japan_stat(Req, Pair):
    
    Current = TradePairs.objects.get(url_title = Pair)    
    ##last value 17520
    List = StockStat.objects.raw("SELECT * FROM main_stockstat WHERE  main_stockstat.Stock_id=%i \
                                  ORDER BY id DESC LIMIT  17520 " % (Current.id) )
    ListJson = []
    VolumeBase = 0
    VolumeTrade = 0
    i = 0
    for item in List:
          StartDate =  item.start_date  
          if i<48:
                VolumeTrade = VolumeTrade + item.VolumeTrade
                VolumeBase = VolumeBase + item.VolumeBase
          i+=1
          Key =  calendar.timegm(StartDate.utctimetuple())
          ListJson.append([int(Key)*1000,  float(item.Start),  float(item.Max), float(item.Min), float(item.End), float(item.VolumeTrade) ])  
    
    OnlineUsersCount =  OnlineUsers.objects.count()
    ListJson.reverse()      
    
    Dict = {"trades":ListJson,
            "online": OnlineUsersCount,
            "volume_base": str(VolumeBase),
            "volume_trade": str(VolumeTrade)}
    
    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ
   
@my_cache
def japan_stat(Req, Pair):
    Current = None
    try:
            Current = TradePairs.objects.get(url_title = Pair)
    except :
            return json_false500(Req)        
        
        
    List = StockStat.objects.raw("SELECT * FROM main_stockstat WHERE  main_stockstat.Stock_id=%i \
                                  ORDER BY id DESC LIMIT 48 " % (Current.id) )
    ListJson = []
    VolumeBase = 0
    VolumeTrade = 0
    for item in List:
          StartDate =  item.start_date  
          VolumeTrade = VolumeTrade + item.VolumeTrade
          VolumeBase = VolumeBase + item.VolumeBase
          Key = "%i:%i" % (StartDate.hour, StartDate.minute)
          ListJson.append([Key,  float(item.Start),  float(item.Max), float(item.Min), float(item.End), float(item.VolumeTrade) ])  
    
    OnlineUsersCount =  OnlineUsers.objects.count()
    ListJson.reverse()      
    
    Dict = {"trades":ListJson,
            "online": OnlineUsersCount,
            "volume_base": str(VolumeBase),
            "volume_trade": str(VolumeTrade)}
    
    RespJ = json.JSONEncoder().encode(Dict)
    return RespJ
                 

##TODO add date filters
@my_cache
def deal_list(Req, Pair):
       
        ResList = common_deal_list(Pair)
        JsonP = json.JSONEncoder().encode(ResList)
        return JsonP


def common_deal_list(Pair, User_id = None):
        
        Current = None
        try:
            Current = TradePairs.objects.get(url_title = Pair)
        except :
            return []
        
        cursor = connection.cursor()
        add_user_filter_str = ""
        if User_id is not  None :
                add_user_filter_str = " AND  main_accounts.user_id = %i " % ( User_id )
               
        
        Query =  cursor.execute("SELECT  main_trans.amnt as amnt,\
                                         main_trans.pub_date as ts,\
                                         price,  \
                                         main_trans.currency_id as currency_id, \
                                         username  as username, \
                                         main_trans.user2_id as trans_owner_id, \
                                         main_orders.user_id as order_owner_id, \
                                         main_orders.sum1_history as order_sum1,\
                                         main_orders.sum2_history as order_sum2 \
                                         FROM main_trans, main_orders, main_accounts, auth_user \
                                         WHERE \
                                         main_orders.trade_pair_id = %i \
                                         AND main_orders.id = main_trans.order_id  \
                                         AND main_accounts.id = main_trans.user2_id \
                                         AND auth_user.id = main_accounts.user_id \
                                         AND main_trans.status='deal' %s\
                                         ORDER BY main_trans.pub_date DESC LIMIT 100" %
                                         ( Current.id, add_user_filter_str) 
                                         
                                         )
        List = dictfetchall(cursor, Query)
        ResList = []
        for item in  List :
            new_item  = process_deal_item( item, Current )
            ResList.append(new_item)
            
        return ResList

@json_auth_required
def my_closed_orders(Req, Pair):
   #if  Req.user.is_authenticated()  and not  Req.user.is_staff:
        ResList = common_deal_list(Pair, Req.user.id)
        Response =  HttpResponse( json.JSONEncoder().encode(ResList) )
        Response['Content-Type'] = 'application/json'
        return Response     

@my_cache
def client_orders(Req, User_id, Title ):
        Dict = {}
        
        Current = None
        try:
            Current = TradePairs.objects.get(url_title = Title)
        except :
            return json_false500(Req)
        
        
        Dict["auth"] = True     
        MyOrders = Orders.objects.raw("SELECT * FROM main_orders WHERE user_id=%i AND ( \
                                        (currency1_id=%i AND currency2_id=%i ) OR  \
                                        (currency2_id=%i AND currency1_id=%i )\
                                        ) AND status='processing' ORDER BY id DESC" %
                                        (User_id,
                                        Current.currency_from.id,
                                        Current.currency_on.id,
                                        Current.currency_from.id,
                                        Current.currency_on.id,
                                        )
                                        )
                                        
        MyOrdersList = []
        c = getcontext()
        c.prec = settings.TRANS_PREC
        
        for i in MyOrders:
                MyOrdersDict = {}
                MyOrdersDict["pub_date"] = formats.date_format(i.pub_date, "DATETIME_FORMAT")
                MyOrdersDict["id"] = i.id
                MyOrdersDict["sum2"] = str(i.sum2)
                MyOrdersDict["sum1"] = str(i.sum1)

                if i.currency1 == Current.currency_on :            
                        MyOrdersDict["type"] = "sell"
                        Number = i.sum2 / i.sum1
                        MyOrdersDict["price"] = format_numbers10(i.price)
                        MyOrdersDict["amnt_trade"] = format_numbers10(i.sum1)
                        MyOrdersDict["amnt_base"] = format_numbers10(i.sum2)
                else:
                        MyOrdersDict["type"] = "buy"
                        Number = i.sum1/ i.sum2
                        MyOrdersDict["price"] = format_numbers10(i.price)
                        MyOrdersDict["amnt_base"] = format_numbers10(i.sum1)
                        MyOrdersDict["amnt_trade"] = format_numbers10(i.sum2)
                MyOrdersList.append(MyOrdersDict)   
                
        balance_sell  =  Accounts.objects.get(user_id = User_id, currency =  Current.currency_on )        
        balance_buy  =  Accounts.objects.get(user_id = User_id, currency =  Current.currency_from )        
        Dict["balance_buy"] = format_numbers_strong(balance_buy.balance )
        Dict["balance_sell"] = format_numbers_strong(balance_sell.balance )
        Dict["your_open_orders"] = MyOrdersList
        RespJ = json.JSONEncoder().encode(Dict)
        return RespJ

@json_auth_required
def my_orders(Req, Title):     
        return client_orders(Req, Req.user.id, Title)     
        
        


def process_deal_item(item, Current):          
    new_item = {}
    new_item["pub_date"] = formats.date_format(item["ts"], "DATETIME_FORMAT") 
    if  int(item["trans_owner_id"] != int(item["order_owner_id"]) ):         
            
            
        rate = item["price"]
        if int(item["currency_id"]) == int(Current.currency_on.id) : 
                new_item["type"] = "buy"
                new_item["user"] = item["username"]
                new_item["price"] = format_numbers10(rate)
                new_item["amnt_base"] = format_numbers10(item["amnt"]*rate)
                new_item["amnt_trade"] = format_numbers10(item["amnt"])     
                        
        else :
                new_item["type"] = "sell"
                new_item["user"] = item["username"]
                new_item["price"] = format_numbers10(rate)
                new_item["amnt_base"] = format_numbers10(item["amnt"])
                new_item["amnt_trade"] = str(item["amnt"]/rate)
                
                
    else :
        rate = item["price"]
        if int(item["currency_id"]) == int(Current.currency_on.id) : 
                new_item["type"] = "buy"
                new_item["user"] = item["username"]
                new_item["price"] = format_numbers10(rate)
                new_item["amnt_base"] = format_numbers10(item["amnt"]/rate)
                new_item["amnt_trade"] = format_numbers10(item["amnt"])     
                        
        else :
                new_item["type"] = "sell"
                new_item["user"] = item["username"]
                new_item["price"] = format_numbers10(rate)
                new_item["amnt_base"] = format_numbers10(item["amnt"])
                new_item["amnt_trade"] = format_numbers10(item["amnt"]*rate)        
    return new_item    


     
def tmpl_context(request, tmpl, Dict):
        
     if not request.user.is_authenticated():
          Dict["is_user"] = False
     else :
          Dict["is_user"] = True   
          Dict = setup_user_menu( request.user, Dict)
          
     Dict["MEDIA_URL"] = settings.MEDIA_URL
     Dict["STATIC_URL"] = settings.STATIC_URL
     Dict["pagetitle"] = settings.pagetitle_main
     Dict["STATIC_SERVER"] = settings.STATIC_SERVER
     
     c = Context(
      Dict
     )
     return HttpResponse(tmpl.render(c))


