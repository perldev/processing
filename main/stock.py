# -*- coding: utf-8 -*-

from django.db import connection

from django.template import Context, loader
from django.http import HttpResponse
from crypton import settings

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from main.models import VolatileConsts, Accounts, TradePairs, Orders, Trans, Currency, Msg, TransError, \
    StockStat, OnlineUsers
from django.views.decorators.cache import cache_page
from main.http_common import caching, cached_json_object
import logging

logger = logging.getLogger(__name__)
from main.models import dictfetchall
from  main.msgs import system_notify
import json
import decimal
from decimal import Decimal, getcontext
import datetime
from main.http_common import caching, cached_json_object


def get_price_bid(cursor, Type, Time):
    Query = cursor.execute(
        "SELECT 100000*(unixtime div 100) as t,\n\
                AVG(price) as p \n\
                FROM  main_btce_trade_stat_minute_usd \n\
                WHERE \n\
                datetime > (now() - interval 30 day)\n\
                AND (unixtime*1000)> %i\n\
                AND ask_bid ='bid' \n\
                AND stock_type = '%s'\n\
                GROUP BY t ORDER BY t " % ( int(Time), Type )
    )
    List = dictfetchall(cursor, Query)
    last = Time
    Result = []
    for i in List:
        Result.append([i["t"], float(i["p"])])
        last = i["t"]
    return Result


def get_price_vol(cursor, Type, Time):
    Query = cursor.execute(
        "SELECT 100000*(unixtime div 100) as t,\n\
                sum(amount) as p \n\
                FROM  main_btce_trade_stat_minute_usd \n\
                WHERE \n\
                datetime > (now() - interval 30 day)\n\
                AND (unixtime*1000)> %i\n\
                AND stock_type = '%s'\n\
                GROUP BY t ORDER BY t " % ( int(Time), Type )
    )
    List = dictfetchall(cursor, Query)
    last = Time
    Result = []
    for i in List:
        Result.append([i["t"], float(i["p"])])
        last = i["t"]
    return (Result, last)


def get_price_ask(cursor, Type, Time):
    Query = cursor.execute(
        "SELECT 100000*(unixtime div 100) as t,\n\
                AVG(price) as p \n\
                FROM  main_btce_trade_stat_minute_usd \n\
                WHERE \n\
                datetime > (now() - interval 30 day)\n\
                AND (unixtime*1000)> %i\n\
                AND ask_bid ='ask' \n\
                AND stock_type = '%s'\n\
                GROUP BY t ORDER BY t " % ( int(Time), Type )
    )
    List = dictfetchall(cursor, Query)
    last = Time
    Result = []
    for i in List:
        Result.append([i["t"], float(i["p"])])
        last = i["t"]

    return Result


def btce_btc_usd(Req, Type, Time):
    CachedKey = 'btce_' + Type + '_stat' + Time
    cache = caching()
    Cached = cache.get(CachedKey, False)
    if Cached:
        return cached_json_object(Cached)

    Dict = {}
    Cursor = connection.cursor()
    AskList = get_price_ask(Cursor, Type, Time)
    BidList = get_price_bid(Cursor, Type, Time)
    (VolList, Last) = get_price_vol(Cursor, Type, Time)
    Dict = {"data_bid": BidList, "data_ask": AskList, "data_vol": VolList, "last": Last}
    RespJ = json.JSONEncoder().encode(Dict)
    if int(Time) > 0:
        cache.set(CachedKey, RespJ, 5)
    else:
        cache.set(CachedKey, RespJ)
    return cached_json_object(RespJ)
