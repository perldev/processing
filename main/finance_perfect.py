# -*- coding: utf-8 -*-

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
from main.models import TransIn, TransOut, Currency, OutRequest, Orders, add_trans
from main.msgs import notify_email

import hashlib
import random
import datetime
from decimal import Decimal, getcontext

from main.http_common import http_tmpl_context, http_json, json_false, json_denied, json_true, denied, setup_custom_meta
from main.http_common import tmpl_context, caching, get_client_ip
from main.http_common import json_auth_required, format_numbers10, format_numbers_strong, format_numbers
from main.http_common import auth_required, g2a_required, json_false500, login_page_with_redirect, format_numbers4

from main import views
import sdk.perfect_money_sdk

if sdk.perfect_money_sdk.enabled:
    from sdk.perfect_money_sdk import perfect_money_sdk
    import sdk.perfect_money_settings
from main.my_cache_key import check_freq
# from sdk.crypto import CryptoAccount
from main.finance_forms import FiatCurrencyTransferForm
from main.finance import emoney_transfer_withdraw_submit
#from sdk.crypto_settings import Settings as SDKCryptoCurrency
from datetime import date
from crypton import my_messages

TITLE = "perfect_money"


@auth_required
def perfect_transfer_withdraw_submit(Req):
    return emoney_transfer_withdraw_submit(Req, TITLE)


@auth_required
def perfect_transfer_withdraw(Req, CurrencyTitle, Amnt):
    Dict = {}
    CurrencyIn = Currency.objects.get(title=CurrencyTitle)
    Dict["currency"] = CurrencyTitle
    Dict["use_f2a"] = False
    if Req.session.has_key("use_f2a"):
        Dict["use_f2a"] = Req.session["use_f2a"]

    t = loader.get_template("ajax_form.html")
    Dict["action"] = "/finance/emoney_transfer_withdraw_submit_perfect"
    Dict["action_title"] = my_messages.withdraw_transfer

    try:
        Last = \
        TransOut.objects.filter(user=Req.user, provider=TITLE, currency=CurrencyIn, status="processed").order_by('-id')[
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


def perfect_start_pay(Req, Currency, Amnt):
    pay_invoice = perfect_money_sdk(Currency,
                                    sdk.perfect_money_settings.PMERCHID,
                                    sdk.perfect_money_settings.PPASSWD,
                                    sdk.perfect_money_settings.PPASSWD2,
    )
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        return pay_invoice.generate_pay_request(Req.user, Amnt)


def perfect_deposit(Req, Currency, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 1:
        raise TransError("pay_requirments")
    pay_invoice = perfect_money_sdk(Currency,
                                    sdk.perfect_money_settings.PMERCHID,
                                    sdk.perfect_money_settings.PPASSWD,
                                    sdk.perfect_money_settings.PPASSWD2)
    return HttpResponse(pay_invoice.generate_button(Amnt))


def perfect_call_back_url(Req, Currency, OrderId):
    pay_call_back = perfect_money_sdk(Currency,
                                      sdk.perfect_money_settings.PMERCHID,
                                      sdk.perfect_money_settings.PPASSWD,
                                      sdk.perfect_money_settings.PPASSWD2
    )
    rlog_req = OutRequest(raw_text=str(Req.REQUEST), from_ip=get_client_ip(Req))
    rlog_req.save()
    return pay_call_back.api_callback_pay(Req.REQUEST, process_perfect_in)


def perfect_call_back_url_fail(Req, OrderId):
    rlog_req = OutRequest(raw_text=str(Req.REQUEST), from_ip=get_client_ip(Req))
    rlog_req.save()
    return redirect("/finance")


def process_perfect_in2(OrderId, Comission):
    order = Orders.objects.get(id=int(OrderId), status='processing2')

    add_trans(order.transit_1, order.sum1, order.currency1,
              order.transit_2, order,
              "payin", None, False)
    if Comission > 0:
        add_trans(order.transit_2, Comission, order.currency1,
                  order.transit_1, order,
                  "comission", None, False)

    order.status = "processed"
    order.save()
    return True


def process_perfect_in(OrderId, Comis, Key):
    order = Orders.objects.get(id=int(OrderId), status="processing")
    order.status = "processing2"
    order.save()
    DebCred = TransIn(currency=order.currency1,
                      amnt=order.sum1,
                      user=order.user,
                      provider=TITLE,
                      comission=Comis,
                      user_accomplished_id=1,
                      status="created",
                      order=order
    )
    DebCred.sign_record(Key)
    DebCred.save()
    process_perfect_in2(OrderId, Comis)
    notify_email(order.user, "deposit_notify", DebCred)
    DebCred.status = 'processed'
    DebCred.save()
    return True
    
