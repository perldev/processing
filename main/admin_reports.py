# -*- coding: utf-8 -*-

from django.shortcuts import render_to_response
from django.template import RequestContext
from main.models import Accounts, OrdersMem, VolatileConsts, Currency, TradePairs
from django.contrib.admin.views.decorators import staff_member_required
from main.http_common import format_numbers_strong
from django.contrib.auth.models import User
from django.db.models import Sum


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

# from sdk.crypto import CryptoAccount



@staff_member_required
def whole_balance(request):
    CurList = Currency.objects.all()

    CurrencyConsist = []
    
    cursor = connection.cursor()
    #<td> {{ item.currency }}</td>
      #<td>{{ item.balance_in }} </td>
      #<td> {{ item.balance_out }}</td>
      #<td> {{ item.balance_orders }}</td>
      #<td> {{ item.balance_acc }}</td>
      #<td>{{ item.balance_corr }}</td> 
      #<td> {{ item.consist }} </td>
      #<td> {{ item.delta }} </td>
    fields = ('balance_out', 'balance_corr')
    
    for cur in CurList:
        item = {'currency': cur.title}
        for field in fields:
            Name_Field = field + "_"+ cur.title
            obj = None
            try:
                obj = VolatileConsts.objects.get(Name=Name_Field)
            except VolatileConsts.DoesNotExist:
                obj = VolatileConsts(Name = Name_Field, Value = "0.0")
                obj.save()
            item[field] = obj.Value
            
        item['balance_orders'] = OrdersMem.objects.filter(status = "processing", currency1=cur.id).aggregate(orders_sum = Sum('sum1'))["orders_sum"]
        if  item['balance_orders'] is None:
            item['balance_orders'] = Decimal("0.0")
        item['balance_acc'] = get_acc_in(cur)
        
        item['balance_out_in'] = Accounts.objects.filter(currency = cur, balance__lte=0).aggregate(acc_sum = Sum('balance'))["acc_sum"]
        
        item['balance_in'] = (item['balance_orders'] + item['balance_acc'])
        
        item['consist'] = item['balance_in'] + item['balance_out_in']
        item['delta'] = Decimal(item['balance_out']) + Decimal(item["balance_corr"]) - item['balance_in']
        CurrencyConsist.append(item)

  

    return render_to_response('admin/main/whole_balance.html',
                              {'balance': CurrencyConsist},
                                context_instance=RequestContext(request))

                                
def get_acc_in(Cur):

    cursor = connection.cursor()
    transit_accounts = []
    for pair in TradePairs.objects.all():
        transit_accounts.append(str(pair.transit_on.id))
        transit_accounts.append(str(pair.transit_from.id))

    ComisId = settings.COMISSION_USER
    if Cur.title == "UAH":
        transit_accounts.append("28") # cardpayments
    
    NotId = ",".join(transit_accounts)
    
    
    # not Credit and not Mistake and not transit accounts
    Query = "SELECT sum(balance) FROM main_accounts \
             WHERE currency_id=%s \
             AND user_id not in (346, 31, %s) AND id not in (%s) AND balance>0 " % (str(Cur.id), ComisId, NotId)

    cursor.execute(Query, [])
    S1 = cursor.fetchone()
    if S1 == (None, ):
        S1 = Decimal("0.0")
    else:
        S1 = S1[0]
        
    return S1
    