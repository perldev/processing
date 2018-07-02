# -*- coding: utf-8 -*-

# Create your views here.
from django.template import Context, loader
from django.http import HttpResponse
from crypton import settings
from main.msgs import send_mail
from django.utils.translation import ugettext_lazy as _
from django.utils import formats

from crypton import my_messages
from django.db import connection
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.models import User
from main.models import add_trans, TransError, Accounts, Currency, ActiveLink, CryptoTransfers, generate_private_sign
from main.models import TradePairs, Orders, Trans, BankTransfers, LiqPayTrans, get_comisP2P, Partnership, OrdersMem, \
    TransOut
from main.http_common import generate_key, my_cached_paging

import hashlib
import random
import datetime
from main.finance_forms import BankTransferForm, LiqPayTransferForm, CurrencyTransferForm, CardP2PTransfersForm, \
    PinForm, FiatCurrencyTransferForm
from decimal import Decimal, getcontext
from main.http_common import http_tmpl_context, http_json, json_false, json_denied, json_true, denied, \
    setup_custom_meta, tmpl_context, caching, get_client_ip
from main.http_common import json_auth_required, format_numbers10, format_numbers_strong, format_numbers, \
    format_numbers4, auth_required, g2a_required, json_false500, login_page_with_redirect

from main.models import dictfetchall, OutRequest, PoolAccounts
from main import views
from sdk.liqpay import liqpay
from sdk.p24 import p24
from sdk.p2p_deposit import P2P_DEPOSIT_OPTS
from main.my_cache_key import check_freq
# from sdk.crypto import CryptoAccount

from sdk.crypto_settings import Settings as SDKCryptoCurrency
from main.models import Accounts, Currency, ActiveLink, TradePairs, Orders, Msg, StaticPage, HoldsWithdraw, \
    CardP2PTransfers
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum
from datetime import date
from main.finance_forms import FiatCurrencyTransferForm
from main.account import get_account

from crypton import my_messages


def confirm_emoney_withdraw_email(Post, Key):
    return _(u"Для подтверждение операции вывода инструментов на кошелек\n\n\
К: {card}\n\
Сумма: {amnt}\n\
Валюта: {currency}\n\n\n\
Перейдите по ссылке {ref}\n\n\
Для ОТМЕНЫ операции перейдите по ссылке {ref1}\n\n\n\
С уважением служба поддержки {project_name}\n\
").format(card=Post["wallet"], amnt=Post["amnt"], currency=Post["currency"],
          ref=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_emoney/" + Key,
          ref1=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_emoney/" + Key + "?do=cancel",
          project_name=settings.PROJECT_NAME
    )


def confirm_p2p_withdraw_email(Post, Key):
    return _(u"Для подтверждение операции вывода инструментов на Карту\n\n\
Карта: {card}\n\
Сумма: {amnt}\n\
Валюта: {currency}\n\n\n\
Перейдите по ссылке {ref}\n\n\
Для ОТМЕНЫ операции перейдите по ссылке {ref1}\n\n\n\
С уважением служба поддержки {project_name}\n\
").format(card=Post["CardNumber"], amnt=Post["amnt"], currency=Post["currency"],
          ref=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_p2p/" + Key,
          ref1=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_p2p/" + Key + "?do=cancel",
          project_name=settings.PROJECT_NAME
    )


def confirm_p2p_withdraw_email_common(Post, Key):
    return _(u"На {project_name} вами заказана  операция вывода инструментов на Карту\n\n\
Карта: {card}\n\
Имя держателя: {name}\n\
Сумма: {amnt}\n\
Валюта: {currency}\n\n\n\
Операция будет проведена  через 30 минут\n\
Для ОТМЕНЫ операции перейдите по ссылке {ref}\n\n\n\
С уважением служба поддержки {project_name}\n\
").format(card=Post["CardNumber"],
          name=Post["CardName"],
          amnt=Post["amnt"],
          currency=Post["currency"],
          ref=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_p2p/" + Key + "?do=cancel",
          project_name=settings.PROJECT_NAME
    )


def confirm_liqpay_withdraw_email(Post, Key):
    return _(u"Для подтверждение операции вывода инструментов на LiqPay\n\n\
Телефон: {phone}\n\
Сумма: {amnt}\n\
Валюта: {currency}\n\n\n\
перейдите по ссылке {ref}\n\n\n\
С уважением служба поддержки {project_name}\n\
").format(phone=Post["phone"],
          amnt=Post["amnt"],
          currency=Post["currency"],
          ref=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_liqpay/" + Key,
          project_name=settings.PROJECT_NAME
    )


def confirm_bank_withdraw_email(Post, Key):
    return _(u"Для подтверждение операции вывода инструментов на банковский счет\n\n\
МФО банка: {mfo}\n\
ОКПО: {okpo}\n\
Счет: {account}\n\
Сумма: {amnt}\n\
Валюта: {currency}\n\n\n\
перейдите по ссылке {ref}\n\n\n\
С уважением служба поддержки {project_name}\n\
").format(mfo=Post["mfo"], okpo=Post["okpo"], account=Post["account"],
          amnt=Post["amnt"], currency=Post["currency"],
          ref=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_bank/" + Key,
          project_name=settings.PROJECT_NAME
    )


def withdraw_p2p_auto(P2P):
    return u"Автоматический вывод инструментов на карту\n\n\
Cтатус: %s\n\
Карта: %s\n\
CardHolder: %s\n\
Сумма: %s\n\
Валюта: %s\n\n\n\
пользователь: %s\n\n\n\
email:%s \n\n\n\
" % ( P2P.status, P2P.CardNumber, P2P.CardName, P2P.amnt, P2P.currency, P2P.user.username, P2P.user.email )


def withdraw_p2p(P2P):
    return u"Вывод инструментов на карту\n\n\
Карта: %s\n\
CardHolder: %s\n\
Сумма: %s\n\
Валюта: %s\n\n\n\
пользователь: %s\n\n\n\
email:%s \n\n\n\
" % ( P2P.CardNumber, P2P.CardName, P2P.amnt, P2P.currency, P2P.user.username, P2P.user.email )


def withdraw_crypto(Transfer):
    return u"Вывод инструментов на кошелек криптовалюты\n\n\
Кошелек: %s\n\
Сумма: %s\n\
Валюта: %s\n\n\n\
" % ( Transfer.account, Transfer.amnt, Transfer.currency )


def confirm_crypto_withdraw_email(Post, Key):
    return _(u"Для подтверждения операции вывода инструментов на кошелек криптовалюты\n\n\
Кошелек: {account}\n\
Сумма: {amnt}\n\
Валюта: {currency}\n\n\n\
перейдите по ссылке {ref}\n\n\n\
С уважением служба поддержки {project_name}\n\
").format(account=Post["wallet"],
          amnt=Post["amnt"],
          currency=Post["currency"],
          ref=settings.BASE_URL + "finance/common_secure_page/confirm_withdraw_currency/" + Key,
          project_name=settings.PROJECT_NAME

    )


#url(r'^finance/liqpay_transfer_withdraw/([\w]+)/([\w]+)','main.finance.liqpay_transfer_withdraw', name='liqpay_transfer_withdraw'),
#url(r'^finance/liqpay_transfer_withdraw_submit$','main.finance.liqpay_transfer_withdraw', name='liqpay_transfer_withdraw'),
#url(r'^finance/bank_transfer_withdraw/([\w]+)/([\w]+)','main.finance.bank_transfer_withdraw', name='bank_transfer_withdraw' ),
#url(r'^finance/bank_transfer_withdraw_submit$','main.finance.bank_transfer_withdraw_submit', name='bank_transfer_withdraw_submit')




@auth_required
def bank_transfer_withdraw(Req, CurrencyTitle, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 10:
        raise TransError("pay_requirments")
    if CurrencyTitle != "UAH":
        raise TransError("pay_requirments")

    Dict = {}
    CurrencyIn = Currency.objects.get(title=CurrencyTitle)
    # TODO add working with ref through Account class
    Account = Accounts.objects.get(user=Req.user, currency=CurrencyIn)
    if Account.reference is None or len(Account.reference) == 0:
        Account.reference = generate_key(settings.BANK_KEY_SALT)
        Account.save()
    Dict["amnt"] = str(Amnt)
    Dict["currency"] = "UAH"
    t = loader.get_template("ajax_form.html")
    Dict["action"] = "/finance/bank_transfer_withdraw_submit"
    Dict["action_title"] = settings.withdraw_transfer
    Dict["common_help_text"] = settings.attention_be_aware
    Form = BankTransferForm(initial=Dict, user=Req.user)
    Dict["form"] = Form.as_p()
    return tmpl_context(Req, t, Dict)


@auth_required
def bank_transfer_withdraw_submit(Req):
    Form = BankTransferForm(Req.POST, user=Req.user)
    Dict = {}
    if Form.is_valid():
        # Save 
        Key = generate_key("bank_withdraw")
        transfer = BankTransfers(
            ref="",
            okpo=Form.cleaned_data["okpo"],
            mfo=Form.cleaned_data["mfo"],
            debit_credit="out",
            account=Form.cleaned_data["account"],
            description=Form.cleaned_data["description"],
            currency=Form.currency_instance,
            amnt=Form.cleaned_data["amnt"],
            user=Req.user,
            comission="0.00",
            confirm_key=Key
        )
        transfer.save()
        #if settings.DEBUG is False:
        send_mail(_(u'Подтверждение вывода  ' + settings.BASE_HOST),
                  confirm_bank_withdraw_email(Form.cleaned_data, Key),
                  [Req.user.email],
                  fail_silently=False)
        return redirect("/finance/confirm_withdraw_msg")
    else:
        t = loader.get_template("simple_form.html")
        Dict["title"] = settings.withdraw_title_bank
        Dict["form"] = Form.as_p()
        Dict["common_help_text"] = settings.attention_be_aware
        Dict["action"] = "/finance/bank_transfer_withdraw_submit"
        Dict["action_title"] = settings.withdraw_transfer
        return tmpl_context(Req, t, Dict)


def crypton_currency_list(user, CurrencyTitle):
    Status = {"auto": _(u"в работе"), "processing": _(u"в работе"), "created": _(u"заявлена"),
              "order_cancel": _(u"отменена"), "canceled": _(u"отменена"),
              "core_error": _(u"Ошибка"), "processed": _(u'исполнен')}
    DbOut = {"in": _(u"Дебет"), "out": _(u"Кредит")}
    for item in CryptoTransfers.objects.filter(currency__title=CurrencyTitle, user_id=user).order_by("-id"):
        Account = item.account
        Account = Account[:4] + "*******" + Account[-4:]
        Cell = (DbOut[item.debit_credit],
                Account,
                item.amnt, item.pub_date,
                Status[item.status], item.confirms, item.crypto_txid  )
        yield {"transes": Cell}


'''
CREATE VIEW  main_uah_in_out AS SELECT pub_date, phone, amnt, comission, user_id, status, debit_credit 
FROM main_liqpaytrans UNION ALL SELECT pub_date, CardNumber, amnt, comission, user_id, status, debit_credit
FROM main_cardp2ptransfers 
UNION ALL SELECT pub_date, "BITCOIN TRADE COMPANY", amnt, comission, user_id, status, debit_credit FROM main_p24transin           
'''


def user_ref_list(UserId):
    for item in Partnership.objects.filter(user_ref_id=UserId):
        Cell = (
            item.user.username,
            item.url_from,
            item.user.date_joined,
            item.income,
            item.income_from
        )
        yield {"transes": Cell}


@auth_required
def refs(request):
    (TransList, TransTitle) = (None, None)

    TransList = user_ref_list(request.user.id)
    TransTitle = ( {"value": _(u"Пользователь")},
                   {"value": _(u"Дата регистрации")},
                   {"value": _(u"Доход от даты")},
                   {"value": _(u"Доход")},
                   {"value": _(u"URL from")}
    )

    Dict = {
        "TransList": TransList,
        "TransTitle": TransTitle,
    }
    tmpl = loader.get_template("finance_partners_list.html")
    return http_tmpl_context(request, tmpl, Dict)


@auth_required
def crypton_emoney_list(user, currency):
    cursor = connection.cursor()
    Query = "SELECT debit_credit,wallet ,amnt, pub_date, status FROM main_emoney_in_out WHERE 1\
                 AND   user_id = %s AND currency_id='%i'  ORDER BY pub_date DESC " % ( str(user), currency.id )

    Status = {"auto": _(u"в работе"),
              "processing": _(u"в работе"),
              "processing2": _(u"в работе"),
              "created": _(u"заявлена"),
              "order_cancel": _(u"отменена"),
              "canceled": _(u"отменена"),
              "core_error": _(u"Ошибка"),
              "processed": _(u'исполнен')}

    DbOut = {"in": _(u"Дебет"),
             "out": _(u"Кредит")}

    Query = cursor.execute(Query)
    List = dictfetchall(cursor, Query)
    for item in List:

        Account = ""
        if item['wallet'] != '':
            Account = item["wallet"]
            Account = "*******" + Account[-4:]

        Cell = (
            DbOut[item["debit_credit"]],
            Account,
            item["amnt"],
            item["pub_date"],
            Status[item["status"]]  )
        yield {"transes": Cell}


@auth_required
def crypton_uah_list(user):
    cursor = connection.cursor()
    Query = "SELECT pub_date, phone, amnt, comission, user_id, status, debit_credit FROM main_uah_in_out WHERE 1\
                 AND   user_id = %s  ORDER BY pub_date DESC " % ( str(user) )

    Status = {"auto": _(u"в работе"),
              "processing": _(u"в работе"),
              "processing2": _(u"в работе"),
              "created": _(u"заявлена"),
              "order_cancel": _(u"отменена"),
              "canceled": _(u"отменена"),
              "core_error": _(u"Ошибка"),
              "processed": _(u'исполнен')}

    DbOut = {"in": _(u"Дебет"),
             "out": _(u"Кредит")}

    Query = cursor.execute(Query)
    List = dictfetchall(cursor, Query)
    for item in List:
        Account = item["phone"]
        Account = Account[:4] + "*******" + Account[-4:]

        Cell = (
            DbOut[item["debit_credit"]],
            Account,
            item["amnt"],
            item["pub_date"],
            Status[item["status"]]  )
        yield {"transes": Cell}


@auth_required
def depmotion_home(Req):
    CurrencyInstance = Currency.objects.all()
    t = loader.get_template("finance_depmotion_home.html")
    Dict = {}
    Dict["CurrencyList"] = CurrencyInstance
    return tmpl_context(Req, t, Dict)


@auth_required
def depmotion(request, CurrencyTitle):
    CurrencyList = Currency.objects.all()
    cur = Currency.objects.get(title=CurrencyTitle)
    (TransList, TransTitle) = (None, None)
    user_id =  request.session["looking_user"]
    if SDKCryptoCurrency.has_key(CurrencyTitle):
        ##TODO avoid this
        TransList = list(crypton_currency_list(user_id, CurrencyTitle))
        TransTitle = (
        {"value": _(u"Дебит/Кредит")}, {"value": _(u"Адрес")}, {"value": _(u"Сумма")}, {"value": _(u"Дата")},
        {"value": _(u"Статус")}, {"value": _(u"Подтверждения")}, {"value": _(u"Txid")}  )
    elif CurrencyTitle == "UAH":
        TransList = list(crypton_uah_list(user_id))
        TransTitle = ({"value": _(u"Дебит/Кредит")}, {"value": _(u"Счет")}, {"value": _(u"Сумма")},
                      {"value": _(u"Дата")}, {"value": _(u"Статус")}  )
    else:
        TransList = list(crypton_emoney_list(user_id, cur))
        TransTitle = ({"value": _(u"Дебит/Кредит")}, {"value": _(u"Сумма")},
                      {"value": _(u"Дата")}, {"value": _(u"Статус")}  )

    TransListPage = None
    paginator = Paginator(TransList, 200)  # Show 25 contacts per page

    page = request.GET.get('page', 1)

    try:
        TransListPage = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        TransListPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        TransListPage = paginator.page(paginator.num_pages)
    # balance =  Balances.objects.get(account = "whole", currency = CurrencyInstance)




    Dict = {
        "paging": True,
        "current_trade": CurrencyTitle,
        "Trans": TransListPage,
        "TransList": TransListPage.object_list,
        "TransTitle": TransTitle,
        "CurrencyList": CurrencyList
    }
    tmpl = loader.get_template("finance_depmotion_home.html")
    return http_tmpl_context(request, tmpl, Dict)


@json_auth_required
def crypto_currency_get_account(Req, CurrencyTitle):
    CurrencyIn = Currency.objects.get(title=CurrencyTitle)
    # TODO add working with ref through Account class
    Account = Accounts.objects.get(user=Req.user, currency=CurrencyIn)
    if Account.reference is not None and Account.reference != "":
        Response = HttpResponse('{"account":\"' + Account.reference + '\"}')
        Response['Content-Type'] = 'application/json'
        return Response
    else:

        FreeAccount = PoolAccounts.objects.filter(currency=CurrencyIn, status="created").first()
        FreeAccount.user = Req.user
        FreeAccount.pub_date = date.today()
        FreeAccount.status = "processing"
        FreeAccount.save()
        Account.reference = FreeAccount.address
        Account.save()
        Response = HttpResponse('{"account":\"' + Account.reference + '\"}')
        Response['Content-Type'] = 'application/json'
        return Response

# DEPRECATED
def confirm_withdraw_bank(Req, S):
    Transfer = BankTransfers.objects.get(user=Req.user, status="created", confirm_key=S)
    ##add trans may be there
    AccountTo = get_account(user=Req.user, currency=Transfer.currency)

    FreqKey = "orders" + str(Req.user.id)
    if not check_freq(FreqKey, 2):
        Response = HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response

        ## if not by reference, but by users
    TradePair = TradePairs.objects.get(url_title="bank_transfers")
    order = Orders(user=Req.user,
                   price=Decimal("1"),
                   currency1=Transfer.currency,
                   currency2=Transfer.currency,
                   sum1_history=Transfer.amnt,
                   sum2_history=Transfer.amnt,
                   sum1=Transfer.amnt,
                   sum2=Transfer.amnt,
                   transit_1=AccountTo.acc(),
                   transit_2=TradePair.transit_from,
                   trade_pair=TradePair,
                   status="created"
    )
    order.save()
    # TODO add process exception in withdraw crypto currency
    add_trans(AccountTo.acc(), Transfer.amnt, Transfer.currency,
              TradePair.transit_from, order, "withdraw", S, False)
    order.status = "processing"
    order.save()
    Transfer.order = order
    Transfer.status = "processing"
    Transfer.save()
    t = loader.get_template("ajax_simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdraw_ok
    Dict["simple_msg"] = settings.withdraw_msg_ok
    return tmpl_context(Req, t, Dict)


@auth_required
def crypto_currency_withdraw(Req, CurrencyTitle):
    Dict = {}
    CurrencyIn = Currency.objects.get(title=CurrencyTitle)
    Dict["currency"] = CurrencyTitle
    Dict["use_f2a"] = False
    if Req.session.has_key("use_f2a"):
        Dict["use_f2a"] = Req.session["use_f2a"]

    t = loader.get_template("ajax_form.html")
    Dict["action"] = "/finance/crypto_currency_withdraw_submit"
    Dict["action_title"] = settings.withdraw_transfer

    try:
        Last = CryptoTransfers.objects.filter(user=Req.user, currency=CurrencyIn, status="processed").order_by('-id')[0]
        #         Dict["wallet"] = Last.account
    except:
        pass

    TradePair = TradePairs.objects.get(currency_on=CurrencyIn,
                                       currency_from=CurrencyIn)
    Dict["common_help_text"] = settings.attention_be_aware_crypto % ( str(TradePair.min_trade_base) )

    Form = CurrencyTransferForm(initial=Dict, user=Req.user)

    Dict["form"] = Form.as_p()
    return tmpl_context(Req, t, Dict)


@auth_required
def crypto_currency_withdraw_submit(Req):
    Dict = {"use_f2a": False}
    if Req.session.has_key("use_f2a"):
        Dict["use_f2a"] = Req.session["use_f2a"]
    Form = CurrencyTransferForm(data=Req.POST, user=Req.user)
    getcontext().prec = settings.TRANS_PREC

    if Form.is_valid():
        # Save 
        Key = generate_key("currency_withdraw")
        Amnt = Decimal(Form.cleaned_data["amnt"]) - Form.comission
        transfer = CryptoTransfers(account=Form.cleaned_data["wallet"],
                                   currency=Form.currency_instance,
                                   amnt=Amnt,
                                   pub_date=datetime.datetime.now(),
                                   comission=Form.comission,
                                   user=Req.user,
                                   confirm_key=Key,
                                   debit_credit="out")
        transfer.save()
        #if settings.DEBUG is False:
        send_mail(_(u'Подтверждение вывода  ') + settings.BASE_HOST,
                  confirm_crypto_withdraw_email(Form.cleaned_data, Key),
                  [Req.user.email],
                  fail_silently=False)

        return redirect("/finance/confirm_withdraw_msg")
    else:
        t = loader.get_template("simple_form.html")
        Dict["form"] = Form.as_p()
        CurrencyIn = Currency.objects.get(title=Form.cleaned_data["currency"])

        Dict["currency"] = Form.cleaned_data["currency"]
        TradePair = TradePairs.objects.get(currency_on=CurrencyIn,
                                           currency_from=CurrencyIn)
        Dict["common_help_text"] = settings.attention_be_aware_crypto % ( str(TradePair.min_trade_base) )
        Dict["action"] = "/finance/crypto_currency_withdraw_submit"
        Dict["action_title"] = settings.withdraw_transfer
        Dict["pin_load"] = not Dict["use_f2a"]
        return tmpl_context(Req, t, Dict)


def confirm_withdraw_currency(Req, S, PrivateKey=''):
    S = S.replace("\n", "").replace(" ", "")
    Transfer = CryptoTransfers.objects.get(status="created", confirm_key=S)
    ##add trans may be there
    AccountTo = get_account(user=Transfer.user, currency=Transfer.currency)
    ## if not by reference, but by users

    TradePair = TradePairs.objects.get(currency_on=Transfer.currency,
                                       currency_from=Transfer.currency)
    FreqKey = "orders" + str(Req.user.id)

    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response

    order = Orders(price=Decimal("1"),
                   user=Transfer.user,
                   currency1=Transfer.currency,
                   currency2=Transfer.currency,
                   sum1_history=Transfer.amnt + Transfer.comission,
                   sum2_history=Transfer.amnt,
                   sum1=Transfer.amnt + Transfer.comission,
                   sum2=Transfer.amnt,
                   transit_1=AccountTo.acc(),
                   transit_2=TradePair.transit_from,
                   trade_pair=TradePair,
                   status="created",
    )
    order.save()

    order.status = "processing"
    order.save()
    Transfer.order = order
    Transfer.status = "processing"
    Transfer.sign_record(PrivateKey)
    Transfer.save()
    # TODO add process exception in withdraw crypto currency
    add_trans(AccountTo.acc(), Transfer.amnt + Transfer.comission, Transfer.currency, TradePair.transit_from,
              order, "withdraw", S, False)

    t = loader.get_template("ajax_simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdraw_ok
    Dict["simple_msg"] = settings.withdraw_msg_ok
    caching().delete("balance_" + str(Transfer.user.id))
    notify_admin_withdraw(withdraw_crypto(Transfer))
    return tmpl_context(Req, t, Dict)


def notify_admin_withdraw(Text):
    try:
        send_mail(u'Вывода  ' + settings.BASE_HOST,
                  Text,
                  [settings.ADMIN_COPY],
                  fail_silently=False)
    except:
        pass


def confirm_withdraw_msg_auto(Req):
    t = loader.get_template("simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdrawing_secondary_main_email_confirmation_title
    Dict["simple_msg"] = _(u"Спасибо за работу, ваши деньги уже в пути")
    return tmpl_context(Req, t, Dict)


def confirm_withdraw_msg(Req):
    t = loader.get_template("simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdrawing_secondary_main_email_confirmation_title
    Dict["simple_msg"] = settings.withdrawing_sending_email_confirmation
    return tmpl_context(Req, t, Dict)


@auth_required
def p2p_transfer_withdraw(Req, CurrencyTitle, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 10:
        raise TransError("pay_requirments")
    if CurrencyTitle != "UAH":
        raise TransError("pay_requirments")

    Dict = {}
    CurrencyIn = Currency.objects.get(title=CurrencyTitle)
    Dict["amnt"] = str(Amnt)
    Dict["currency"] = CurrencyTitle

    try:
        Last = CardP2PTransfers.objects.filter(user=Req.user, status="processed").order_by('-id')[0]
        Dict["CardNumber"] = Last.CardNumber
        Dict["CardName"] = Last.CardName
    except:
        pass

    t = loader.get_template("ajax_form.html")
    Dict["action"] = "/finance/p2p_transfer_withdraw_submit"
    Dict["action_title"] = settings.p2p_transfer
    Dict["common_help_text"] = settings.p2p_attention_be_aware
    Form = CardP2PTransfersForm(initial=Dict, user=Req.user)
    Dict["form"] = Form.as_p()
    return tmpl_context(Req, t, Dict)


def p2p_transfer_withdraw_secure(Req, Form):
    Key = generate_key("p2p_ahuihui")
    CardNumber = Form.cleaned_data["CardNumber"]
    CardNumber = CardNumber.replace(" ", "")
    Transfer = CardP2PTransfers(
        debit_credit="out",
        CardName=Form.cleaned_data["CardName"],
        CardNumber=CardNumber,
        currency=Form.currency_instance,
        amnt=Form.cleaned_data["amnt"],
        user=Req.user,
        pub_date=datetime.datetime.now(),
        confirm_key=Key
    )
    FreqKey = "orders" + str(Req.user.id)
    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response

    Transfer.save()

    AccountTo = get_account(user=Req.user, currency=Transfer.currency)
    ## if not by reference, but by users
    TradePair = TradePairs.objects.get(url_title="p2p_transfers")
    order = Orders(user=Req.user,
                   price=Decimal("1"),
                   currency1=Transfer.currency,
                   currency2=Transfer.currency,
                   sum1_history=Transfer.amnt,
                   sum2_history=Transfer.amnt,
                   sum1=Transfer.amnt,
                   sum2=Transfer.amnt,
                   transit_1=AccountTo.acc(),
                   transit_2=TradePair.transit_from,
                   trade_pair=TradePair,
                   status="created"
    )
    order.save()
    # TODO add process exception in withdraw p2p
    add_trans(AccountTo.acc(), Transfer.amnt, Transfer.currency, TradePair.transit_from,
              order, "withdraw", Key, False)
    order.status = "processing"
    order.save()
    Transfer.order = order
    Transfer.save()


    #if settings.DEBUG is False:
    send_mail(_(u'Подтверждение вывода  ') + settings.BASE_HOST,
              confirm_p2p_withdraw_email(Form.cleaned_data, Key),
              [Req.user.email],
              fail_silently=False)


def p2p_transfer_withdraw_common_operation(Req, Form):
    Key = generate_key("p2p_ahuihui")
    CardNumber = Form.cleaned_data["CardNumber"]
    CardNumber = CardNumber.replace(" ", "")
    Amnt = Form.cleaned_data["amnt"]
    NewAmnt = get_comisP2P(CardNumber, Decimal(Amnt))
    Transfer = None
    FreqKey = "orders" + str(Req.user.id)

    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response

    if NewAmnt < 0:
        Transfer = CardP2PTransfers(
            debit_credit="out",
            CardName=Form.cleaned_data["CardName"],
            CardNumber=CardNumber,
            currency=Form.currency_instance,
            amnt=Amnt,
            pub_date=datetime.datetime.now(),
            user=Req.user,
            confirm_key=Key,
            status="processing2")
        Transfer.sign_record(settings.COMMON_SALT)

    if NewAmnt > 0:
        Transfer = CardP2PTransfers(
            debit_credit="out",
            CardName=Form.cleaned_data["CardName"],
            CardNumber=CardNumber,
            currency=Form.currency_instance,
            amnt=Amnt,
            pub_date=datetime.datetime.now(),
            user=Req.user,
            confirm_key=Key,
            status="auto"
        )
        Transfer.sign_record(settings.COMMON_SALT)

    AccountTo = get_account(user=Req.user, currency=Transfer.currency)
    ## if not by reference, but by users
    TradePair = TradePairs.objects.get(url_title="p2p_transfers")
    order = Orders(user=Req.user,
                   price=Decimal("1"),
                   currency1=Transfer.currency,
                   currency2=Transfer.currency,
                   sum1_history=Transfer.amnt,
                   sum2_history=Transfer.amnt,
                   sum1=Transfer.amnt,
                   sum2=Transfer.amnt,
                   transit_1=AccountTo.acc(),
                   transit_2=TradePair.transit_from,
                   trade_pair=TradePair,
                   status="created"
    )
    order.save()
    # TODO add process exception in withdraw p2p
    add_trans(AccountTo.acc(), Transfer.amnt, Transfer.currency, TradePair.transit_from,
              order, "withdraw", Key, False)

    order.status = "processing"
    order.save()
    Transfer.order = order
    Transfer.save()
    notify_admin_withdraw(withdraw_p2p_auto(Transfer))

    send_mail(_(u'Подтверждение вывода  ') + settings.BASE_HOST,
              confirm_p2p_withdraw_email_common(Form.cleaned_data, Key),
              [Req.user.email],
              fail_silently=False)


def emoney_transfer_withdraw_secure(Req, Form, provider):
    Key = generate_key("p2p_ahuihui")
    Wallet = Form.cleaned_data["wallet"]
    Wallet = Wallet.replace(" ", "")
    Transfer = TransOut(
        wallet=Wallet,
        currency=Form.currency_instance,
        amnt=Form.cleaned_data["amnt"],
        user=Req.user,
        pub_date=datetime.datetime.now(),
        confirm_key=Key,
        provider=provider
    )
    FreqKey = "orders" + str(Req.user.id)
    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response

    Transfer.save()

    AccountTo = get_account(user=Req.user, currency=Transfer.currency)
    ## if not by reference, but by users
    trade_pair_title = provider + "_" + Form.currency_instance.title.lower()
    TradePair = TradePairs.objects.get(url_title=trade_pair_title)
    order = Orders(user=Req.user,
                   price=Decimal("1"),
                   currency1=Transfer.currency,
                   currency2=Transfer.currency,
                   sum1_history=Transfer.amnt,
                   sum2_history=Transfer.amnt,
                   sum1=Transfer.amnt,
                   sum2=Transfer.amnt,
                   transit_1=AccountTo.acc(),
                   transit_2=TradePair.transit_from,
                   trade_pair=TradePair,
                   status="created"
    )
    order.save()
    # TODO add process exception in withdraw p2p
    add_trans(AccountTo.acc(), Transfer.amnt, Transfer.currency, TradePair.transit_from,
              order, "withdraw", Key, False)
    order.status = "processing"
    order.save()
    Transfer.order = order
    Transfer.save()


    #if settings.DEBUG is False:
    send_mail(_(u'Подтверждение вывода  ') + settings.BASE_HOST,
              confirm_emoney_withdraw_email(Form.cleaned_data, Key),
              [Req.user.email],
              fail_silently=False)


@auth_required
def emoney_transfer_withdraw_submit(Req, provider):
    Form = FiatCurrencyTransferForm(Req.POST, user=Req.user)
    Dict = {}
    if Form.is_valid():
        ##check if it common operation
        #Last = list(TransOut.objects.filter(user = Req.user,
        #wallet = Form.cleaned_data["wallet"] ,
        #provider= provider,
        #status="processed").order_by('-id') )
        #if len(Last) > 0 :
        #emoney_transfer_withdraw_common_operation(Req, Form)
        #return redirect("/finance/confirm_withdraw_msg")
        #else:
        emoney_transfer_withdraw_secure(Req, Form, provider)
        return redirect("/finance/confirm_withdraw_msg_auto")


    else:
        t = loader.get_template("simple_form.html")
        Dict["action"] = "/finance/emoney_transfer_withdraw_submit_" + provider
        Dict["action_title"] = my_messages.emoney_transfer
        Dict["common_help_text"] = my_messages.emoney_attention_be_aware
        Dict["form"] = Form.as_p()
        return tmpl_context(Req, t, Dict)


@auth_required
def p2p_transfer_withdraw_submit(Req):
    Form = CardP2PTransfersForm(Req.POST, user=Req.user)
    Dict = {}
    if Form.is_valid():
        ##check if it common operation
        Last = list(CardP2PTransfers.objects.filter(user=Req.user,
                                                    CardNumber=Form.cleaned_data["CardNumber"],
                                                    status="processed").order_by('-id'))
        if len(Last) > 0:
            p2p_transfer_withdraw_common_operation(Req, Form)
            return redirect("/finance/confirm_withdraw_msg_auto")

        else:
            p2p_transfer_withdraw_secure(Req, Form)
            return redirect("/finance/confirm_withdraw_msg")

                        


    else:
        t = loader.get_template("simple_form.html")
        Dict["action"] = "/finance/p2p_transfer_withdraw_submit"
        Dict["action_title"] = settings.p2p_transfer
        Dict["common_help_text"] = settings.p2p_attention_be_aware
        Dict["form"] = Form.as_p()
        return tmpl_context(Req, t, Dict)


def confirm_withdraw_emoney(Req, S, PrivateKey):
    Transfer = TransOut.objects.get(user=Req.user,
                                    confirm_key=S,
                                    status='created')

    IsCancel = Req.REQUEST.get("do", None)
    if Transfer.status == "created" and IsCancel is not None:
        Transfer.status = "canceled"
        Transfer.save()
        order = Transfer.order
        order.status = "canceled"
        order.save()
        add_trans(order.transit_2, Transfer.amnt, Transfer.currency, order.transit_1,
                  order, "canceled", S, False)

        t = loader.get_template("simple_msg.html")
        Dict = {}
        Dict["title"] = settings.withdraw_cancel
        Dict["simple_msg"] = settings.withdraw_msg_cancel
        caching().delete("balance_" + str(Req.user.id))
        return tmpl_context(Req, t, Dict)

    if Transfer.status != "created":
        raise TransError("hacker " + Req.user.username)
        ##add trans may be there
    Transfer.status = "processing"
    Transfer.sign_record(PrivateKey)
    Transfer.save()
    t = loader.get_template("ajax_simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdraw_ok
    Dict["simple_msg"] = settings.withdraw_msg_ok
    return tmpl_context(Req, t, Dict)


def confirm_withdraw_p2p(Req, S, PrivateKey=''):
    Transfer = CardP2PTransfers.objects.get(user=Req.user,
                                            confirm_key=S,
                                            status='created')

    IsCancel = Req.REQUEST.get("do", None)
    if (Transfer.status == "processing" or Transfer.status == "auto" or Transfer.status == "created") and IsCancel is not None:
        Transfer.status = "canceled"
        Transfer.save()
        order = Transfer.order
        order.status = "canceled"
        order.save()
        add_trans(order.transit_2, Transfer.amnt, Transfer.currency, order.transit_1,
                  order, "canceled", S, False)

        t = loader.get_template("simple_msg.html")
        Dict = {}
        Dict["title"] = settings.withdraw_cancel
        Dict["simple_msg"] = settings.withdraw_msg_cancel
        caching().delete("balance_" + str(Req.user.id))
        return tmpl_context(Req, t, Dict)

    if Transfer.status != "created":
        raise TransError("hacker " + Req.user.username)



        ##add trans may be there
    Transfer.status = "processing"
    Transfer.sign_record(PrivateKey)
    Transfer.save()
    t = loader.get_template("ajax_simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdraw_ok
    Dict["simple_msg"] = settings.withdraw_msg_ok
    notify_admin_withdraw(withdraw_p2p(Transfer))
    return tmpl_context(Req, t, Dict)

#DEPRECATED
@auth_required
def liqpay_transfer_withdraw(Req, CurrencyTitle, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 10:
        raise TransError("pay_requirments")
    if CurrencyTitle != "UAH":
        raise TransError("pay_requirments")

    Dict = {}
    CurrencyIn = Currency.objects.get(title=CurrencyTitle)

    Account = get_account(user=Req.user, currency=CurrencyIn)
    Acc = Account.acc()
    if Acc.reference is None or len(Acc.reference) == 0:
        Account.reference = generate_key(settings.BANK_KEY_SALT)
        Account.save()

    Dict["amnt"] = str(Amnt)
    Dict["currency"] = "UAH"
    try:
        Last = LiqPayTrans.objects.filter(user=Req.user, status="processed").order_by('-id')[0]
        Dict["phone"] = Last.phone
    except:
        pass

    t = loader.get_template("ajax_form.html")
    Dict["action"] = "/finance/liqpay_transfer_withdraw_submit"
    Dict["action_title"] = settings.withdraw_transfer
    Dict["common_help_text"] = settings.liqpay_attention_be_aware
    Form = LiqPayTransferForm(initial=Dict, user=Req.user)

    Dict["form"] = Form.as_p()
    return tmpl_context(Req, t, Dict)


@auth_required
def liqpay_transfer_withdraw_submit(Req):
    Form = LiqPayTransferForm(Req.POST, user=Req.user)
    Dict = {}
    if Form.is_valid():
        # Save 
        Key = generate_key("liqpay_withdraw")
        transfer = LiqPayTrans(
            debit_credit="out",
            phone=Form.cleaned_data["phone"],
            description=Form.cleaned_data["description"],
            currency=Form.currency_instance,
            amnt=Form.cleaned_data["amnt"],
            user=Req.user,
            pub_date=datetime.datetime.now(),
            comission="0.000",
            confirm_key=Key
        )
        transfer.save()
        #if settings.DEBUG is False:
        send_mail(_(u'Подтверждение вывода  ') + settings.BASE_HOST,
                  confirm_liqpay_withdraw_email(Form.cleaned_data, Key),
                  [Req.user.email],
                  fail_silently=False)
        return redirect("/finance/confirm_withdraw_msg")
    else:
        t = loader.get_template("simple_form.html")
        Dict["title"] = settings.withdraw_title_liqpay
        Dict["form"] = Form.as_p()
        Dict["common_help_text"] = settings.attention_be_aware
        Dict["action"] = "/finance/liqpay_transfer_withdraw_submit"
        Dict["action_title"] = settings.withdraw_transfer
        return tmpl_context(Req, t, Dict)

# DEPRECATED
def confirm_withdraw_liqpay(Req, S):
    Transfer = LiqPayTrans.objects.get(user=Req.user,
                                       status="created",
                                       confirm_key=S)
    liqpay_class = liqpay("ru", Transfer.currency.title)
    FreqKey = "orders" + str(Req.user.id)
    if not check_freq(FreqKey, 3):
        Response = HttpResponse('{"status":false}')
        Response['Content-Type'] = 'application/json'
        return Response

        ##add trans may be there
    AccountTo = get_account(user=Req.user, currency=Transfer.currency)
    ## if not by reference, but by users
    TradePair = liqpay_class.get_traid_pair()
    order = Orders(user=Req.user,
                   price=Decimal("1"),
                   currency1=Transfer.currency,
                   currency2=Transfer.currency,
                   sum1_history=Transfer.amnt,
                   sum2_history=Transfer.amnt,
                   sum1=Transfer.amnt,
                   sum2=Transfer.amnt,
                   transit_1=AccountTo.acc(),
                   transit_2=TradePair.transit_from,
                   trade_pair=TradePair,
                   status="created"
    )
    order.save()
    add_trans(AccountTo.acc(), Transfer.amnt, Transfer.currency, TradePair.transit_from,
              order, "withdraw", S, False)
    order.status = "processing"
    order.save()
    Transfer.order = order
    Transfer.status = "processing"
    Transfer.save()
    t = loader.get_template("ajax_simple_msg.html")
    Dict = {}
    Dict["title"] = settings.withdraw_ok
    Dict["simple_msg"] = settings.withdraw_msg_ok
    caching().delete("balance_" + str(Req.user.id))

    return tmpl_context(Req, t, Dict)


def p2p_deposit(Req, Cur, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 1:
        raise TransError("pay_requirments")
    Dict = {}
    t = loader.get_template("p2p_transfer_req.html")
    CurrencyIn = Currency.objects.get(title=Cur)
    Account = get_account(user=Req.user, currency=CurrencyIn)
    Dict["account"] = P2P_DEPOSIT_OPTS[Cur]
    Acc = Account.acc()
    if Acc.acc().reference is None or len(Acc.acc().reference) == 0:
        Account.reference = generate_key("bank_pp", 16)
        Account.save()
    Dict["description"] = _(u"Оплата информационных услуг в счет публичного договора #" + Acc.reference)
    Dict["amnt"] = str(Amnt)

    return tmpl_context(Req, t, Dict)


##at this moment only for UAH
def bank_deposit(Req, Cur, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 1:
        raise TransError("pay_requirments")
    Dict = {}
    t = loader.get_template("bank_transfer_req.html")
    Dict["okpo"] = settings.BANK_UAH_OKPO
    Dict["mfo"] = settings.BANK_UAH_MFO
    Dict["account"] = settings.BANK_UAH_ACCOUNT
    CurrencyIn = Currency.objects.get(title=Cur)
    # TODO add working with ref through Account class
    Account = Accounts.objects.get(user=Req.user, currency=CurrencyIn)
    if Account.reference is None or len(Account.reference) == 0:
        Account.reference = generate_key(settings.BANK_KEY_SALT)
        Account.save()
    Dict["description"] = _(u"Оплата информационных услуг в счет публичного договора #%s" + Account.reference)
    Dict["amnt"] = str(Amnt)

    return tmpl_context(Req, t, Dict)


def p24_start_pay(Req, Amnt):
    pay_invoice = p24("UAH", "https://api.privatbank.ua/", settings.P24_MERCHID2, settings.P24_PASSWD2)
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        return pay_invoice.generate_pay_request(Req.user, Amnt)


def p24_deposit(Req, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 100:
        raise TransError("pay_requirments")
    pay_invoice = p24("UAH", "https://api.privatbank.ua/", settings.P24_MERCHID2, settings.P24_PASSWD2)
    return HttpResponse(pay_invoice.generate_button(Amnt))


def p24_call_back_url(Req, OrderId):
    pay_call_back = p24("UAH", "https://api.privatbank.ua/", settings.P24_MERCHID2, settings.P24_PASSWD2)
    rlog_req = OutRequest(raw_text=str(Req.REQUEST), from_ip=get_client_ip(Req))
    rlog_req.save()
    return pay_call_back.api_callback_pay(Req.REQUEST, OrderId)


def liqpay_start_pay(Req, Amnt):
    pay_invoice = liqpay("ru", "UAH")
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        return pay_invoice.generate_pay_request(Req.user, Amnt)


def liqpay_call_back_url(Req, OrderId):
    pay_call_back = liqpay("ru", "UAH")
    rlog_req = OutRequest(raw_text=str(Req), from_ip=get_client_ip(Req))
    rlog_req.save()

    return pay_call_back.api_callback_pay(Req.REQUEST)


def liqpay_deposit(Req, Amnt):
    amnt = Decimal(Amnt)
    if amnt < 100:
        raise TransError("pay_requirments")
    pay_invoice = liqpay("ru", "UAH")
    return HttpResponse(pay_invoice.generate_button(Amnt))


def setup_user_menu(Dict):
    return Dict


def home(Req):
    if not Req.user.is_authenticated():
        return login_page_with_redirect(Req)
    else:
        t = loader.get_template("finance.html")
        Dict = {}
        # it is not an actual information
        user_id =  request.session["looking_user"]

        All = Accounts.objects.filter(user_id=user_id).order_by('-currency__ordering')
        BalancesOrders = OrdersMem.objects.filter(user_id=user_id,
                                                  status="processing") 
        OrdersBalances = {}
        for currency in BalancesOrders:
            if OrdersBalances.has_key(currency.currency1):
                OrdersBalances[currency.currency1] += currency.sum1
            else:
                OrdersBalances[currency.currency1] = currency.sum1
        
        ResAcc = []
        for i in All:
            item = {}
            i.balance = format_numbers_strong(i.balance)
            item["balance"] = i.balance
            currency_id = i.currency.id
            item["currency"] = i.currency
            if OrdersBalances.has_key(currency_id):
                item["on_orders"] = format_numbers_strong(OrdersBalances[currency_id])
            ResAcc.append(item)

        Dict["page_accounts"] = ResAcc
        return tmpl_context(Req, t, Dict)


def generate_description(DictAccounts, item):
    
    if item.status == 'payin':
        return _(u"Deposit filling")
    if item.status == 'withdraw':
        return _(u"Withdraw money from account")
    if item.status == 'order_cancel':
        return _(u"Canceletion of deal order ")
        
    if item.status == 'canceled':
        return _(u"Canceletion of operation")
    
    if item.status == 'bonus':
        return _(u"Partnership reward")

    if item.status == 'deal_return':
        return _(u"Return unused funds according with deal order  ") #.format(order_id=item.order_id)

    if item.status == 'deposit':
        return _(u"Deposit funds according with order ") #.format(order_id=item.order_id)

    if item.status == 'comission':
        return _(u" Commision from the deal in order ") #.format(order_id=item.order_id)
    if item.status == 'deal':
        return _(u" Buying   according with the order ") #.format(order_id=item.order_id)


@auth_required
def trans(Req):
    t = loader.get_template("finance_trans.html")
    Dict = {}
    user_id =  request.session["looking_user"]
    ListAccounts = []
    DictAccounts = {}
    for i in Accounts.objects.filter(user_id=user_id):
        ListAccounts.append(str(i.id))
        DictAccounts[i.id] = 1
    AccountsStr = ",".join(ListAccounts)

    Query = "SELECT * FROM main_trans WHERE 1 \
                               AND status in ('payin','deposit','withdraw','deal','order_cancel','comission','bonus','deal_return')\
                               AND ( user1_id IN (%s) OR user2_id IN  (%s) ) ORDER BY id DESC  " % (
    AccountsStr, AccountsStr)

    List = Trans.objects.raw(Query)
    All = []
    for item in List:

        new_item = {}
        new_item["description"] = generate_description(DictAccounts, item)
        new_item["amnt"] = format_numbers_strong(item.amnt)
        new_item["currency"] = item.currency.title

        new_item["ts"] = int((item.pub_date - datetime.datetime(1970,1,1)).total_seconds())
        new_item["id"] = item.id
        new_item["in"] = False
        if DictAccounts.has_key(item.user2_id):
            new_item["in"] = True
        All.append(new_item)

    page = Req.GET.get('page', 1)

    PageObject = my_cached_paging("user_id_trans" + str(user_id), Trans, page, All)

    Dict["trans_list"] = PageObject.object_list
    Dict["paging"] = PageObject

    return tmpl_context(Req, t, Dict)


def common_confirm_page(Req, Order):
    rlog_req = OutRequest(raw_text=str(Req.REQUEST), http_referer=Req.META.get("HTTP_REFERER", ""),
                          from_ip=get_client_ip(Req))
    rlog_req.save()

    OrderData = Orders.objects.get(id=int(Order))
    if OrderData.status == "created":
        OrderData.status = "wait_secure"
        OrderData.save()

    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        t = loader.get_template("finance_confirm_liqpay_page.html")
        Dict = {"order": Order}
        return tmpl_context(Req, t, Dict)


@auth_required
def open_orders(Req, TradePair="btc_uah"):
    t = loader.get_template("finance_open_deals.html")
    Dict = {}
    Dict["current_stock"] = TradePair
    Dict["trade_pair"] = TradePair

    Dict = views.setup_trades_pairs(TradePair, Dict)
    return tmpl_context(Req, t, Dict)


@auth_required
def deals(Req, TradePair="btc_uah"):
    t = loader.get_template("finance_deals.html")
    Dict = {}
    Dict["current_stock"] = TradePair
    Dict["trade_pair"] = TradePair
    Dict = views.setup_trades_pairs(TradePair, Dict)
    return tmpl_context(Req, t, Dict)


@auth_required
def common_secure_page(Req, Type, Key):
    Use = False
    IsCancel = Req.REQUEST.get("do", None)

    Avalible = {
        "confirm_withdraw_bank": confirm_withdraw_bank,
        "confirm_withdraw_currency": confirm_withdraw_currency,
        "confirm_withdraw_liqpay": confirm_withdraw_liqpay,
        "confirm_withdraw_p2p": confirm_withdraw_p2p,
        "confirm_withdraw_emoney": confirm_withdraw_emoney
    }

    if IsCancel == "cancel":
        return Avalible[Type](Req, Key)

    if Req.session.has_key("use_f2a"):
        Use = Req.session["use_f2a"]

    t = loader.get_template("common_secure_page.html")
    Dict = {}
    Dict["type"] = Type
    Dict["key"] = Key
    Dict["pin_load"] = not Use
    Dict["use_f2a"] = Use
    return tmpl_context(Req, t, Dict)


@auth_required
@g2a_required
def common_secure_confirm(Req):
    Use2fa = False
    if Req.session.has_key("use_f2a"):
        Use2fa = Req.session["use_f2a"]

    if not Use2fa:
        Form = PinForm(Req.REQUEST, user=Req.user)

        if Form.is_valid():
            return call_custom_function(Req, Form.fields["pin"].value)
        else:
            return json_false500(Req)
    else:
        return call_custom_function(Req)


def call_custom_function(Req, PrePrivateKey):
    Avalible = {
        "confirm_withdraw_bank": confirm_withdraw_bank,
        "confirm_withdraw_currency": confirm_withdraw_currency,
        "confirm_withdraw_liqpay": confirm_withdraw_liqpay,
        "confirm_withdraw_p2p": confirm_withdraw_p2p,
        "confirm_withdraw_emoney": confirm_withdraw_emoney

    }
    #try:
    Type = Req.REQUEST.get("key_type")
    HttpRefferer = Req.META['HTTP_REFERER']
    D = HttpRefferer.split("/")
    Key = D[-1:][0]
    if HttpRefferer.find(settings.BASE_HOST) == -1:
        return json_false500(Req)

    return Avalible[Type](Req, Key, PrePrivateKey)
    #except :
    #return json_false500(Req)

#def liqpay_deposit(Req):

#if not Req.user.is_authenticated():
#Response =   HttpResponse('{"status":"auth_error"}')
#Response['Content-Type'] = 'application/json'
#return Response
#else:
#Amnt  = Decimal( Req.REQUEST.get("amnt") )
#CurrencyOn = int( Req.REQUEST.get("currency") )
#Account = Accounts.objects.get(currency = CurrencyOn, user = Req.user )
#Account = Accounts.objects.get(currency = CurrencyOn, user_id = settings.aquiring_user )
                
               
                
                
                       
        
        
        
