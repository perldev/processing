__author__ = 'bogdan'
from main.tornado.api import market_prices, high_japan_stat, japan_stat, buy_list, sell_list, buy, sell, auth, ask, bid, \
    sell
from main.tornado.api import remove_order, my_orders, order_status, deal_list, user_balance, my_closed_orders, \
    cache_control
from main.tornado.api import day_stat, last_price
from main.tornado.api import StopHandler

from crypton.http import CommonRequestHandler, CommonRequestHandlerOneParam, CommonRequestHandlerOneParamNonThread

application_urls_deals = [
    (r'/api/buy/([\w]+)', CommonRequestHandlerOneParamNonThread, dict(callable_object=buy, name='buy')),
    (r'/api/ask/([\w]+)', CommonRequestHandlerOneParamNonThread, dict(callable_object=ask, name='ask')),
    (r'/api/bid/([\w]+)', CommonRequestHandlerOneParamNonThread, dict(callable_object=bid, name='bid')),
    (r'/api/sell/([\w]+)', CommonRequestHandlerOneParamNonThread, dict(callable_object=sell, name='sell')),    
]

application_urls = [
    (r'/stop', StopHandler),
    (r'/cache', CommonRequestHandler, dict(callable_object=cache_control,
                                           name='cache_control')),
    (r'/api/market_prices', CommonRequestHandler, dict(callable_object=market_prices,
                                                       name='market_prices')),
    (r'/api/japan_stat/high/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=high_japan_stat,
                                                                         name='japan_stat')),
    (r'/api/japan_stat/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=japan_stat, name='japan_stat')),
    (r'/api/trades/buy/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=buy_list, name='buy_list')),
    (r'/api/trades/sell/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=sell_list, name='sell_list')),
    (r'/api/auth', CommonRequestHandler, dict(callable_object=auth, name='auth')),
    (r'/api/last_price/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=last_price, name='last_price')),
    (r'/api/day_stat/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=day_stat, name='day_stat')),
    (r'/api/remove/order/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=remove_order,
                                                                      name='remove_order')),
    (r'/api/my_orders/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=my_orders,
                                                                   name='my_orders')),
    (r'/api/order/status/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=order_status,
                                                                      name='order_status')),
    (r'/api/deals/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=deal_list,
                                                               name='deal_list')),
    (r'/api/balance', CommonRequestHandler, dict(callable_object=user_balance,
                                                 name='user_balance')),
    (r'/api/my_deals/([\w]+)', CommonRequestHandlerOneParam, dict(callable_object=my_closed_orders,
                                                                  name='my_closed_orders')),
]
