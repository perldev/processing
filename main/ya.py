# -*- coding: utf-8 -*-

enabled = False
# Create your views here.
from django.template import Context, loader
from django.http import HttpResponse
from crypton import my_messages
from django.core.mail import send_mail
from django.utils.translation import ugettext_lazy as _
from django.utils import formats

from django.db import connection
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.models import User
from main.http_common import generate_key, my_cached_paging
from main.models import TransIn, TransOut, Currency, Accounts, TradePairs, Orders, OutRequest, add_trans

import hashlib
import random
import datetime
from decimal import Decimal, getcontext
from main.http_common import http_tmpl_context, http_json, json_false, json_denied, json_true, denied, \
    setup_custom_meta, tmpl_context, caching, get_client_ip
from main.http_common import json_auth_required, format_numbers10, format_numbers_strong, format_numbers, \
    format_numbers4, auth_required, g2a_required, json_false500, login_page_with_redirect
from main.msgs import notify_email
from main import views

if enabled:
    import sdk.ya_settings

from main.my_cache_key import check_freq
# from sdk.crypto import CryptoAccount
from main.finance_forms import FiatCurrencyTransferForm

#from sdk.crypto_settings import Settings as SDKCryptoCurrency
from datetime import date
from crypton import my_messages, settings
import json


@auth_required
def transfer_withdraw_submit(Req):
    return emoney_transfer_withdraw_submit(Req, "ya")


@auth_required
def transfer_withdraw(Req, CurrencyTitle, Amnt):
    Dict = {}
    CurrencyIn = Currency.objects.get(title="RUR")
    Dict["currency"] = CurrencyIn.title
    Dict["use_f2a"] = False
    if Req.session.has_key("use_f2a"):
        Dict["use_f2a"] = Req.session["use_f2a"]

    t = loader.get_template("ajax_form.html")
    Dict["action"] = "/finance/emoney_transfer_withdraw_submit_ya"
    Dict["action_title"] = my_messages.withdraw_transfer

    try:
        Last = \
        TransOut.objects.filter(user=Req.user, provider="ya", currency=CurrencyIn, status="processed").order_by('-id')[
            0]
        Dict["wallet"] = Last.account
    except:
        pass

    Form = FiatCurrencyTransferForm(initial=Dict, user=Req.user)

    Dict["form"] = Form.as_p()
    return tmpl_context(Req, t, Dict)


def confirm_withdraw_msg_auto(Req):
    t = loader.get_template("simple_msg.html")
    Dict = {}
    Dict["title"] = my_messages.withdrawing_secondary_main_email_confirmation_title
    Dict["simple_msg"] = _(u"Спасибо за работу, ваши деньги уже в пути")
    return tmpl_context(Req, t, Dict)


def confirm_withdraw_msg(Req):
    t = loader.get_template("simple_msg.html")
    Dict = {}
    Dict["title"] = my_messages.withdrawing_secondary_main_email_confirmation_title
    Dict["simple_msg"] = my_messages.withdrawing_sending_email_confirmation
    return tmpl_context(Req, t, Dict)


def deposit(Req, Currency, Amnt):
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        return generate_button(Amnt)


def generate_button(Amnt):
    Data = "<form id='pay_form' action=\"https://money.yandex.ru/quickpay/confirm.xml\" method=\"POST\">\
<p>\
    <input type=\"hidden\" name=\"receiver\" value=\"%s\"/>\
    <input type=\"hidden\" id='sum' name=\"sum\" value=\"%s\" />\
    <input type=\"hidden\"  id=\"ok_return_success\" name=\"ok_return_success\" value=\"\">\
    <input type=\"hidden\"  id=\"ok_return_fail\" name=\"ok_return_fail\" value=\"\">\
    <input type=\"hidden\" id=\"paymentType \" name=\"paymentType \" value=\"PC\">\
    <input type=\"hidden\" id=\"label\" name=\"label\" value=\"\">\
    <input type=\"hidden\"  name=\"quickpay-form\" value=\"shop\">\
    <input type=\"hidden\"  name=\"targets\" value=\"pay in on account\">\
    <input type=\"hidden\"  name=\"short-dest\" value=\"%s\">\
    <input type=\"hidden\"  name=\"formcomment \" value=\"%s\">\
    <input id='ya_submit_button' type=\"submit\"  value=\"%s\" \
     class=\"btn btn-success pull-right\" style=\"margin-right: 11em;\">\
</p>\
</form>" % (sdk.ya_settings.ACCOUNT, Amnt, settings.PROJECT_NAME, settings.PROJECT_NAME,  _(u"Оплатить"),  )
    return HttpResponse(Data)


def generate_result_url(order, User, Amount):
    return settings.BASE_URL + "finance/common_confirm_page/" + str(order.id)


def generate_api_result_url(order, User, Amount):
    return settings.BASE_URL + "finance/ya/hui_hui_hui/" + str(order.id)


@json_auth_required
def start_pay(Req, CurrencyTitle, Amnt):
    AmountStr = Decimal(Amnt)
    User = Req.user
    currency = CurrencyIn = Currency.objects.get(title=CurrencyTitle)
    user_account = Accounts.objects.get(user=User, currency=currency)
    if AmountStr < 0:
        raise TransError("NegativeAmount")

    trade_pair = TradePairs.objects.get(url_title="ya_" + CurrencyTitle.lower())
    if AmountStr < trade_pair.min_trade_base:
        raise TransError("MinAmount")

    order = Orders(user=User,
                   currency1=currency,
                   currency2=currency,
                   price=AmountStr,
                   sum1_history=AmountStr,
                   sum2_history=AmountStr,
                   sum1=AmountStr,
                   sum2=AmountStr,
                   transit_1=trade_pair.transit_on,
                   transit_2=user_account,
                   trade_pair=trade_pair,
                   status="processing"
    )
    order.save()
    ResultUrl = generate_result_url(order, User, Amnt)
    ServerResultUrl = generate_api_result_url(order, User, Amnt)

    Dict = {
        "order_id": str(order.id),
        "result_url": ResultUrl,
        "type": "ya",
        "ext_details": "none",
        "currency": currency.title,
        "server_url": ServerResultUrl,
        "amount": str(AmountStr)
    }

    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    return Response


def call_back_url(Req):
    #        ok_invoice
    #        ok_txn_status
    rlog_req = OutRequest(raw_text=str(Req.REQUEST), from_ip=get_client_ip(Req))
    rlog_req.save()
    FactAmnt = Decimal(Req.REQUEST["amount"])
    body = Req.body
    sha1_hash = Req.REQUEST['sha1_hash']
    if sha1_hash != signature(Req.REQUEST, sdk.ya_settings.SECRET):
        return json_false(Req)

    if process_in(Req.REQUEST["label"], FactAmnt, Decimal("0.0"), settings.COMMON_SALT):
        return json_true(Req)
    else:
        return json_false(Req)


def signature(req_dict, secret):
    #notification_type&operation_id&amount&currency&datetime&sender&codepro&notification_secret&label
    string = "{0}&{1}&{2}&{3}&{4}&{5}&{6}&{7}&{8}".format(req_dict['notification_type'],
                                                          req_dict['operation_id'],
                                                          req_dict['amount'], req_dict['currency'],
                                                          req_dict['datetime'], req_dict['sender'],
                                                          req_dict['codepro'], secret, req_dict['label'])
    hash_object = hashlib.sha1(string)
    return hash_object.hexdigest()


def call_back_url_fail(Req, OrderId):
    return json_false(Req)


def process_in2(OrderId, FactAmnt, Comis):
    order = Orders.objects.get(id=int(OrderId), status='processing2')

    order.status = "processed"
    order.save()
    add_trans(order.transit_1, FactAmnt, order.currency1,
              order.transit_2, order,
              "payin", None, False)
    if Comis > 0:
        add_trans(order.transit_2, Comis, order.currency1,
                  order.transit_1, order,
                  "comission", None, False)

    return True


def process_in(OrderId, FactAmnt, Comis, Key):
    order = Orders.objects.get(id=int(OrderId), status="processing")
    order.status = "processing2"
    order.save()
    DebCred = TransIn(currency=order.currency1,
                      amnt=FactAmnt,
                      user=order.user,
                      provider='ya',
                      comission=Comis,
                      user_accomplished_id=1,
                      status="created",
                      order=order
    )
    DebCred.sign_record(Key)
    DebCred.save()
    process_in2(OrderId, FactAmnt, Comis)
    notify_email(order.user, "deposit_notify", DebCred)
    return True
