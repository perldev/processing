# -*- coding: utf-8 -*-

# Create your views here.
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from crypton import settings
from crypton import my_messages
from django.utils.translation import ugettext

from main.msgs import notify_email, notify_email_admin, send_mail
from main.http_common import http_tmpl_context, http_json, json_false, json_denied, json_true, denied, setup_user_menu, \
    generate_key_from
from main.http_common import generate_key, caching, get_memory_var, json_false500, json_auth_required, \
    format_numbers_strong, format_numbers4
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.utils.translation import ugettext as _
from django.db import connection
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from main.user_forms import UsersRegis, UsersForgotMail
from django.contrib.auth.models import User
from main.models import Accounts, Currency, ActiveLink, TradePairs, Orders, Msg, StaticPage, HoldsWithdraw, CustomMeta, \
    VolatileConsts
from main.models import CustomSettings, UserCustomSettings, NewsPage, PinsImages, new_pin4user, Balances, Partnership, \
    ApiKeys

from sdk.g2f import auth
from django.db.models import Count

from django.views.decorators.cache import cache_page

from datetime import datetime
import hashlib
import random
import json
from decimal import Decimal, getcontext
from main.models import dictfetchall, store_registration

from django.utils import translation


def set_lang(Req, Lang="ru"):
    translation.activate(Lang)
    Req.session[settings.LANGUAGE_COOKIE_NAME] = Lang
    Response = HttpResponseRedirect(Req.META["HTTP_REFERER"])
    Response.set_cookie(settings.LANGUAGE_COOKIE_NAME, Lang)
    return Response


@cache_page(3600)
def crypto_balances_home(request):
    t = loader.get_template("crypto_open_balances.html")
    Dict = {}
    Dict["pagetitle"] = _(u"Публичная информация о балансах криптовалют")
    Dict["CurrencyList"] = Currency.objects.exclude(id=1)
    return http_tmpl_context(request, t, Dict)


@cache_page(3600)
def crypto_balances(request, CurrencyTitle):
    ###TODO add generator
    CurrencyInstance = Currency.objects.get(title=CurrencyTitle)
    BalancesList = []
    for item in Balances.objects.filter(currency=CurrencyInstance).exclude(account="whole").order_by("-balance"):
        Cell = []
        Cell.append(item.account)
        Cell.append(format_numbers_strong(item.balance))
        BalancesList.append({"transes": Cell})

    paginator = Paginator(BalancesList, 200)  # Show 25 contacts per page

    page = request.GET.get('page', 1)
    try:
        BalancesListPage = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        BalancesListPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        BalancesListPage = paginator.page(paginator.num_pages)
    balance = Balances.objects.get(account="whole", currency=CurrencyInstance)
    Dict = {"trans_page_title": _(u"Балансы  {currency} - общий {balance}").format(currency=CurrencyTitle,
                                                                                   balance=format_numbers_strong(
                                                                                       balance.balance)),
            "paging": True,
            "Trans": BalancesListPage,
            "TransList": BalancesListPage.object_list,
            "TransTitle": [{"value": _(u"Адрес")}, {"value": _(u"Баланс")}]
    }
    tmpl = loader.get_template("common_trans_page.html")
    return http_tmpl_context(request, tmpl, Dict)


def register_new_user_mail(User, LinkKey):
    Url = settings.BASE_URL + "fin_regis/" + LinkKey
    return _(u" Для завершения регистрации на {host}\n\
Перейдите пожайлуста по ссылке {url}\n\
Имя пользователя: \"{username}\" \n \
\n\n\n\
С уважением служба поддержки {project_name}\
                ").format(host=settings.BASE_HOST, url=Url, 
                          username=User.username, project_name=settings.PROJECT_NAME)


def ya_metric(Req):
    Str = "<html>\n\
<head><meta http-equiv=\"Content-Type\" content=\"text/html; charset=UTF-8\"></head>\n\
<body>Verification: 474f8051b6db0c25</body>\n\
</html>"

    Response = HttpResponse(Str)
    Response['Content-Type'] = 'text/plain'
    return Response


def robots(Req):
    Str = "User-agent: * \n\
Disallow: /index.html \n\
Disallow: /cabinet \n\
Disallow: /feedback \n\
Disallow: /admin/ \n\
Disallow: /*?* \n\
Disallow: /project/1 \n\
Disallow: /undefined/ \n\
Disallow: /index.php \n\
Disallow: /index.htm \n\
Disallow: /index.asp \n\
Disallow: /node/ \n\
Disallow: /finance/ \n\
Disallow: /main/ \n\
Disallow: /home/ \n\
Disallow: /home.php \n\
Disallow: /home.htm \n\
Disallow: /home.html \n\
Host: {host} \n\
Sitemap: https://{host}/sitemap.xml\n".format(host=settings.BASE_HOST)
    Response = HttpResponse(Str)
    Response['Content-Type'] = 'text/plain'
    return Response


def sitemap(Req):
    tmpl = loader.get_template("sitemap.html")
    c = Context({"host": settings.BASE_URL})
    Resp = HttpResponse(tmpl.render(c))
    Resp["Content-Type"] = 'text/xml'
    return Resp


def check2fa(user):
    Setting = None
    SettingType = CustomSettings.objects.get(title="g2a")
    try:
        Setting = UserCustomSettings.objects.get(user=user, setting=SettingType)
    except UserCustomSettings.DoesNotExist:
        return False

    if Setting.value == "no":
        return False

    return Setting.value


def login_page(request):
    if request.user.is_authenticated():
        return redirect("/stock")
    t = loader.get_template("login_page.html")
    Dict = {}
    return http_tmpl_context(request, t, Dict)


@json_auth_required
def login_f2a_operation(request):
    password = request.REQUEST.get('password', None)
    UserIdCachedInt = request.user.id
    Setting = UserCustomSettings.objects.get(user_id=UserIdCachedInt, setting__title="g2a")
    if auth(Setting.value, password):
        cache = caching()
        Key = "f2a_" + generate_key("fa_")
        cache.set(Key, UserIdCachedInt, 20)
        return HttpResponse(Key)
    return json_false500(request)

# TODO move to frontserver
def time(Req):
    Dict = {"use_f2a": False}

    cache = caching()
    if Req.user.is_authenticated():
        Dict["logged"] = True

        if Req.session.has_key("deal_comission"):

            Dict["deal_comission"] = Req.session["deal_comission_show"]
        else:

            ComisObj = UserCustomSettings.objects.get(user_id=Req.user.id, setting__title="deal_comission")
            DealComission = format_numbers4(Decimal(ComisObj.value) * Decimal("100"))
            Req.session["deal_comission_show"] = DealComission
            Req.session["deal_comission"] = format_numbers4(Decimal(ComisObj.value))
            Dict["deal_comission"] = DealComission

        if Req.session.has_key("use_f2a"):

            Dict["use_f2a"] = Req.session["use_f2a"]
        else:
            Dict["use_f2a"] = False
    else:
        Dict["deal_comission"] = "0.10"

    if Req.session.session_key is not None:
        cache.set("chat_" + Req.session.session_key, Req.user.username, 60000)

    Dict["usd_uah_rate"] = get_memory_var("usd_uah_rate")
    Dict["time"] = (datetime.now() - datetime(1970,1,1)).total_seconds() # datetime.now().strftime("%d.%m.%y %H:%M:%S")
    Dict["sessionid"] = Req.session.session_key
    return json_true(Req, Dict)


def my_custom_error_view(request):
    t = loader.get_template('simple_msg.html')
    return http_tmpl_context(request, t, {"title": _("500,хм..."),
                                          "msg": _(u"Произошла какая-то странная ошибка,\
                                                    и мы о ней уже знаем, и побежали исправлять")})


def login_f2a(request):
    key = request.REQUEST.get('key', None)
    password = request.REQUEST.get('password', None)
    cache = caching()
    UserIdCached = cache.get(key, False)
    if not UserIdCached:
        return json_false500(request)

    UserIdCachedInt = int(UserIdCached)
    Setting = UserCustomSettings.objects.get(user_id=UserIdCachedInt, setting__title="g2a")

    if auth(Setting.value, password):

        user = User.objects.get(id=UserIdCachedInt)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        request.result_auth = "good"
        request.session['auth_user_computered'] = True
        request.session['use_f2a'] = True
        request.session['user_id'] = user.id
        request.session['username'] = user.username
        request.session['email'] = user.email
        ComisObj = UserCustomSettings.objects.get(user_id=request.user.id, setting__title="deal_comission")
        DealComission = format_numbers4(Decimal(ComisObj.value) * Decimal("100"))
        request.session["deal_comission_show"] = DealComission
        request.session["deal_comission"] = format_numbers4(Decimal(ComisObj.value))

        notify_email(user, "auth_notify", request)

        return HttpResponse("good")

    else:
        return json_false500(request)


def try_login(request):
    username = request.REQUEST.get('login')
    password = request.REQUEST.get('password')
    usr = None
    # try:
    usr = User.objects.get(email=username)
    #except User.DoesNotExist:
    #   request.result_auth = "bad"
    #   return HttpResponse("bad")

    user = authenticate(username=usr.username, password=password)
    if user is not None:
        if user.is_active is True:

            if not check2fa(user):
                login(request, user)
                request.result_auth = "good"
                request.session['auth_user_computered'] = True
                request.session['use_f2a'] = False
                request.session['user_id'] = user.id
                ComisObj = UserCustomSettings.objects.get(user_id=request.user.id, setting__title="deal_comission")
                DealComission = format_numbers4(Decimal(ComisObj.value) * Decimal("100"))
                request.session["deal_comission_show"] = DealComission
                request.session["deal_comission"] = format_numbers4(Decimal(ComisObj.value))
                request.session['username'] = user.username
                request.session['email'] = user.email
                notify_email(user, "auth_notify", request)
                return HttpResponse("good")
            else:
                cache = caching()
                key = "2fa_%s" % (generate_key("2fa_"))
                cache.set(key, user.id, 300)
                return HttpResponse(key)

        else:
            request.result_auth = "bad"
            notify_email(user, "auth_notify", request)
            return HttpResponse("bad")
    else:
        notify_email_admin(request, "try_login")
        return HttpResponse("very_bad")


def try_logout(request):
    logout(request)
    notify_email(request.user, "auth_notify", "logout")
    return redirect('/stock')


def user_panel(request, Title="btc_uah"):
    if not request.user.is_authenticated():
        return HttpResponse("very_bad")
    else:
        Current = TradePairs.objects.get(url_title=Title)
        t = loader.get_template("mobile_user_menu.html")

        Dict = setup_user_menu(request.user)
        Dict["is_user"] = True
        Dict["Currency"] = Current.currency_on.title
        Dict["Currency1"] = Current.currency_from.title
        c = Context(
            Dict
        )
        return HttpResponse(t.render(c))


def page_discuss(Req, Id):
    Dict = {}
    Res = StaticPage.objects.get(id=int(Id))
    Dict["page"] = Res
    t = loader.get_template("page_discuss.html")
    return http_tmpl_context(Req, t, Dict)


def page_help(Req):
    Dict = {}
    t = loader.get_template("page_help.html")
    Dict["title"] = settings.help_page
    return http_tmpl_context(Req, t, Dict)


def page(Req, Name):
    Dict = {}
    Res = StaticPage.objects.get(eng_title=Name)
    Dict["page"] = Res
    Dict["keywords"] = Res.meta_keyword
    Dict["description"] = Res.meta_description
    t = loader.get_template("page.html")
    return http_tmpl_context(Req, t, Dict)


def news_cat(Req, i):
    t = loader.get_template("news_page.html")
    return http_tmpl_context(Req, t, {"category": i})


def news(Req):
    t = loader.get_template("news_page.html")
    return http_tmpl_context(Req, t, {})


def news_cat_api(Req, i):
    total = NewsPage.objects.filter(cat_id=i).count()

    Encoder = json.JSONEncoder()
    to = Req.GET.get('limit', 5)
    offset = Req.GET.get('offset', 0)

    items = []
    for i in NewsPage.objects.filter(cat_id=i)[offset:to]:
        text = i.text
        words = text.split()
        desc = " ".join(words[:50])
        items.append({"title": i.title, "description": desc, "url": "/news/" + i.eng_title})
    RespJ = json.JSONEncoder().encode({"total": total, "rows": items})

    return HttpResponse(RespJ)


# https://bitmoney.trade/news_api?order=asc&limit=10&offset=0
def news_api(Req):
    total = NewsPage.objects.all().count()

    Encoder = json.JSONEncoder()
    to = Req.GET.get('limit', 5)
    offset = Req.GET.get('offset', 0)

    items = []
    for i in NewsPage.objects.all()[offset:to]:
        text = i.text
        words = text.split()
        desc = " ".join(words[:50])
        items.append({"title": i.title, "description": desc, "url": "/news/" + i.eng_title})
    RespJ = json.JSONEncoder().encode({"total": total, "rows": items})

    return HttpResponse(RespJ)


#https://bitmoney.trade/news_api?order=asc&limit=10&offset=0

def news_one(Req, Name):
    Dict = {}
    Res = NewsPage.objects.get(eng_title=Name)
    Dict["page"] = Res
    Dict["keywords"] = Res.meta_keyword
    Dict["description"] = Res.meta_description
    t = loader.get_template("page.html")
    return http_tmpl_context(Req, t, Dict)


# url(r'^news$', 'main.views.news', name='news'),               
#    url(r'^news/([\w]+)$', 'main.views.news_one', name='news_one'),  
#    url(r'^news_api$', 'main.views.news_api', name='news_api'),         



def registration_ref(Req, Reference=None):
    if Req.user.is_authenticated():
        return redirect("/stock")

    Req.session['reference'] = Reference

    t = loader.get_template("registration.html")
    Dict = {}
    Dict["title"] = settings.secondary_main

    regisForm = UsersRegis(initial={"reference": Reference})
    Dict["regis_form"] = regisForm.as_p()
    return http_tmpl_context(Req, t, Dict)


def registration(Req):
    if Req.user.is_authenticated():
        return redirect("/stock")
    t = loader.get_template("registration.html")
    Dict = {}
    Dict["title"] = settings.secondary_main
    Reference = Req.session.get('reference', False)
    if Reference:
        regisForm = UsersRegis(initial={"reference": Reference})
    else:
        regisForm = UsersRegis()

    Dict["regis_form"] = regisForm.as_p()

    return http_tmpl_context(Req, t, Dict)


def regis_new_user(Req, Form):
    (new_user, rand_key) = store_registration(Form.cleaned_data['username'],
                                              Form.cleaned_data['email'],
                                              Form.cleaned_data['password1'],
                                              Form.cleaned_data.get('reference', False),
                                              Req.session.get('reference_from', False)
    )

    Req.session['auth_user_computered'] = True
    Email = Form.cleaned_data["email"]
    #if settings.DEBUG is False:
    send_mail(_(u'Регистрация на бирже ' + settings.BASE_HOST),
              register_new_user_mail(new_user, rand_key),
              [Email, settings.ADMIN_COPY],
              fail_silently=False)


def new_api_key(one_user):
    Key1 = generate_key()
    Key2 = generate_key()
    PrivateKey = generate_key_from(Key1, one_user.email)
    new_obj = ApiKeys(public_key=Key2, private_key=PrivateKey, user=one_user)
    new_obj.save()


def fin_regis(Req, key):
    #try :
    f = ActiveLink.objects.get(key=key, status="created")
    f.user.is_active = True
    f.user.save()
    f.status = "processed"
    f.save()
    new_api_key(f.user)

    t = loader.get_template("finished_success_registration.html")
    new_pin = PinsImages(user=f.user)
    f.user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(Req, f.user)
    ShowKey = new_pin4user(new_pin, f.user)
    Dict = {}
    Dict["title"] = settings.secondary_regis_finish_success
    Dict["pin"] = ShowKey
    return http_tmpl_context(Req, t, Dict)
    #except: 
    #    t = loader.get_template("finished_error_registration.html")   
    #    Dict = {}
    #    Dict["title"] = settings.secondary_regis_finish_error
    #    return http_tmpl_context(Req, t, Dict)     


def regis_success(Req):
    t = loader.get_template("success_registration.html")
    Dict = {}
    Dict["title"] = settings.secondary_regis_success
    return http_tmpl_context(Req, t, Dict)


def try_regis(Req):
    Form = UsersRegis(Req.POST)

    if Form.is_valid():
        # Save a new Article object from the form's data.
        regis_new_user(Req, Form)
        return redirect("/regis_success")

    else:
        t = loader.get_template("registration.html")
        Dict = {}
        Dict["title"] = settings.secondary_regis
        Dict["regis_form"] = Form.as_p()
        return http_tmpl_context(Req, t, Dict)


def setup_trades_pairs(Title, Dict=None):
    if Dict is None:
        Dict = {}

    ListCurrency = []
    Current = TradePairs.objects.get(url_title=Title)
    List = list(TradePairs.objects.filter(status="processing").order_by("ordering"))
    Base = List[0].currency_from.long_title
    # ListCurrency.append( {"is_title": True, "title" : Base } )

    for item in List:

        if item.currency_from.long_title != Base:
            # ListCurrency.append({"is_title": True, "title" : item.currency_from.long_title})
            Base = item.currency_from.long_title

        try:
            Price = VolatileConsts.objects.get(Name=item.url_title + "_top_price")
            item.top_price = Price.Value
        except:
            item.top_price = "None"

        ListCurrency.append(item)

    Dict["Currency1"] = Current.currency_from
    Dict["min_deal"] = format_numbers_strong(Current.min_trade_base)
    Dict["Currency"] = Current.currency_on
    Dict["CurrencyTrade"] = ListCurrency

    return Dict


# DEPRECATED
def setup_deals(Req, Title, Dict):
    Current = TradePairs.objects.get(url_title=Title)
    cursor = connection.cursor()
    Query = cursor.execute("SELECT  main_trans.amnt as amnt, main_trans.pub_date as ts,\
                                         currency_id, \
                                         main_orders.sum1_history as order_sum1,\
                                         main_orders.sum2_history as order_sum2 \
                                         FROM main_trans, main_orders \
                                         WHERE \
                                         main_orders.trade_pair_id = %i \
                                         AND main_orders.id = main_trans.order_id  \
                                         AND main_trans.status='deal'\
                                         ORDER BY main_trans.pub_date DESC LIMIT 100" %
                           ( Current.id ))
    List = dictfetchall(cursor, Query)

    for item in List:
        item["pub_date"] = item["ts"]
        if int(item["currency_id"]) == int(Current.currency_on.id):
            item["type"] = "buy"
            rate = item["price"]
            item["price"] = rate
            item["sum2"] = item["amnt"] * rate
            item["sum1"] = item["amnt"]
        else:
            item["type"] = "sell"
            rate = item["price"]
            item["price"] = rate
            item["sum2"] = item["amnt"]
            item["sum1"] = item["amnt"] / rate

    Dict["deals"] = List
    return Dict


def index(Req):
    t = loader.get_template("home.html")
    Dict = {}
    Dict["pagetitle"] = settings.pagetitle_main
    Dict["title"] = settings.pagetitle_home
    return http_tmpl_context(Req, t, Dict)


def home(request):
    # two cases of
    if request.session.get('auth_user_computered', False):
        Path = request.session.get('auth_user_path', None)
        if Path is not None:
            return redirect(Path)
        else:
            return stock(request)

    return index(request)


def stock(Req, Title="btc_uah"):
    if Title is None:
        Title = Req.session.get('stock_path', None)
        if Title is None:
            Title = "btc_uah"
            Req.session['stock_path'] = Title

    t = loader.get_template("index.html")

    Dict = setup_trades_pairs(Title)
    # Dict = setup_common_orders(Req, Title, Dict )
    Dict["current_stock"] = Title
    Dict["title"] = settings.secondary_main
    Dict["trade_pair"] = Title
    Dict["help"] = True
    Dict["usd_uah_rate"] = get_memory_var("usd_uah_rate")
    Req.session['stock_path'] = Title

    return http_tmpl_context(Req, t, Dict)


