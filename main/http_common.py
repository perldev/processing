# -*- coding: utf-8 -*-
from django.http import HttpResponse
from django.utils.translation import ugettext
from django.template import Context, loader
import main.models
import json
from crypton import settings
from crypton import my_messages
import hashlib
import random
from django.core.cache import get_cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import base64

import urllib2
import socket

# def makebold(fn):
#def wrapped():
#return "<b>" + fn() + "</b>"
#return wrapped

#def makeitalic(fn):
#def wrapped():
#return "<i>" + fn() + "</i>"
#return wrapped

#@makebold
#@makeitalic
#def hello():
#return "hello habr"

#print hello() ## выведет <b><i>hello habr</i></b>

def exclude_caching(Path):
    return Path.startswith("/finance")


def delete_show_pin(Key):
    if Key is None:
        return
    cache = caching()
    CachedKey = "pin_" + Key
    #in seconds
    cache.delete(CachedKey)


def start_show_pin(i, tm):
    cache = caching()
    Key = generate_key("pins_")
    CachedKey = "pin_" + Key
    #in seconds
    cache.set(CachedKey, i, tm)
    return Key


def g2a_required(func2decorate):
    def wrapper(*args):
        Request = args[0]

        if not Request.session.has_key('use_f2a'):
            return func2decorate(*args)

        if not Request.session['use_f2a']:
            return func2decorate(*args)

        cache = caching()
        CachedKey = False
        if Request.META.has_key("g2a_session"):
            CachedKey = Request.META.get("g2a_session", False)

        if not CachedKey:
            CachedKey = Request.COOKIES.get("g2a_session", False)

        if not CachedKey:
            CachedKey = Request.REQUEST.get("g2a_session", False)

        if not CachedKey:
            return json_false500(Request)

        Cached = cache.get(CachedKey, False)
        #if not Cached :
        #return json_false500(Request)

        if int(Cached) != int(Request.user.id):
            return json_false500(Request)

        cache.delete(CachedKey)
        return func2decorate(*args)

    return wrapper


def json_auth_required(func2decorate):
    def wrapper(*args):
        Request = args[0]
        if not Request.user.is_authenticated() or not Request.user.is_active:
            return json_false500(Req)

        return func2decorate(*args)

    return wrapper


def auth_required_with_login(func2decorate):
    def wrapper(*args):
        Request = args[0]
        if not Request.user.is_authenticated():
            return login_page_with_redirect(Request)
        return func2decorate(*args)

    return wrapper


def auth_required(func2decorate):
    def wrapper(*args):
        Request = args[0]
        if not Request.user.is_authenticated() or not Request.user.is_active:
            return login_page_with_redirect(Request)

        return func2decorate(*args)

    return wrapper


class AuthError(Exception):
    def __init__(self):
        self.value = "auth error"

    def __str__(self):
        return repr(self.value)


### TODO move this to cache
def check_api_sign(PublicKey, Sign, Body):
    Settings = main.models.get_api_settings(PublicKey)
    if Sign != generate_key_from2(Body, Settings.private_key):
        raise AuthError()
    return Settings.user


def json_auth_required(func2decorate):
    def wrapper(*args):
        Req = args[0]
        PublicKey = None

        try:
            PublicKey = Req.META['HTTP_PUBLIC_KEY']
        except:
            if not Req.user.is_authenticated() or not Req.user.is_active:
                return json_false500(Req)
            return func2decorate(*args)

        try:
            Sign = Req.META['HTTP_API_SIGN']
            ##required param
            OutOrderId = Req.REQUEST.get('out_order_id')
            Nonce = Req.REQUEST.get('nonce')
            cache = caching()
            OldNonce = cache.get("nonce_" + PublicKey)
            if int(OldNonce) >= int(Nonce):
                return json_false500(Req, {"description": "invalid_nonce"})
            else:
                cache.set("nonce_" + PublicKey, Nonce, 50000)

            Req.user = check_api_sign(PublicKey, Sign, Req.body)
        except AuthError as e:
            return json_false500(Req, {"auth": False})
        except:
            return json_false500(Req, {"description": "some common"})
        return func2decorate(*args)

    return wrapper


def my_cache_fail(func2decorate):
    def wrapper(*args):
        size = len(args)
        CachedKey = func2decorate.func_name
        cache = caching()
        for arg in range(1, size):
            CachedKey = CachedKey + "_" + str(args[arg])

        Cached = cache.get(CachedKey, False)
        if Cached:
            return cached_json_object(Cached)

        return json_false500(Req, {"description": "not in cache"})

    return wrapper


def my_cache(func2decorate):
    def wrapper(*args):
        size = len(args)
        CachedKey = func2decorate.func_name
        cache = caching()
        for arg in range(1, size):
            CachedKey = CachedKey + "_" + str(args[arg])

        Cached = cache.get(CachedKey, False)
        if Cached:
            return cached_json_object(Cached)

        RespJ = func2decorate(*args)
        cache.set(CachedKey, RespJ)
        return cached_json_object(RespJ)

    return wrapper


def format_numbers4(D):
    return "%.3f" % ( D )


def format_numbers(D):
    return "%.5f" % ( D )


def format_numbers10(D):
    return "%.10f" % ( D )


def format_numbers_strong(D):
    s = "%.12f" % ( D )
    return s[:-2]


def status_false():
    Response = HttpResponse(json.JSONEncoder().encode({"status": False}))
    Response['Content-Type'] = 'application/json'
    return Response


def cached_json_object(RespJ):
    Response = HttpResponse(RespJ)
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'
    return Response


def caching():
    return get_cache('default')


##exports http_tmpl_context, http_json, json_false, json_denied, json_true, denied, setup_custom_meta, setup_user_menu

def get_memory_var(NameVal):
    try:
        Var = main.models.VolatileConsts.objects.get(Name=NameVal)
        return Var.Value
    except:
        return ""


def setup_user_menu(User, Dict=None):
    if Dict is None:
        Dict = {}
    All = main.models.Accounts.objects.filter(user=User).order_by('-currency__ordering')

    for i in All:
        i.balance = format_numbers10(i.balance)

    Dict["new_msg_count"] = main.models.Msg.objects.filter(user_to=User,
                                                           user_hide_to="false",
                                                           user_seen_to="false").exclude(user_from_id=1).count()

    Dict["new_notfication_count"] = main.models.Msg.objects.filter(user_to=User,
                                                                   user_from_id=1,
                                                                   user_hide_to="false",
                                                                   user_seen_to="false").count()
    Dict["username"] = User.username
    Dict["accounts"] = All

    return Dict


def generate_key_from2(Val, Salt):
    m = hashlib.sha256()
    m.update(Val + Salt)
    return m.hexdigest()


def generate_key_from(Val, Salt):
    m = hashlib.sha256()
    m.update(Salt + Val)
    return m.hexdigest()


def generate_key(Salt="", length=64):
    m = hashlib.sha256()
    m.update(Salt + str(random.randrange(1, 1000000000000000000)))
    s = m.hexdigest()
    return s[:length]


def tmpl_context(request, tmpl, Dict):
    if not request.user.is_authenticated():
        Dict["is_user"] = False
    else:
        Dict["is_user"] = True
        Dict["username"] = request.user.username
        Dict = setup_user_menu(request.user, Dict)

    Dict["news_cats"] = main.models.Category.objects.all().order_by("ordering")
    Dict["project_name"] = settings.PROJECT_NAME
    Dict["MEDIA_URL"] = settings.MEDIA_URL
    Dict["STATIC_URL"] = settings.STATIC_URL
    Dict["pagetitle"] = my_messages.pagetitle_main
    Dict = setup_custom_meta(request, Dict)
    Dict["STATIC_SERVER"] = settings.STATIC_SERVER

    if not exclude_caching(request.get_full_path()):
        request.session['auth_user_path'] = request.get_full_path()

    Reference = request.GET.get('ref', False)
    if Reference:
        request.session['reference'] = Reference
        if request.META.has_key("HTTP_REFERER"):
            request.session['reference_from'] = request.META["HTTP_REFERER"]
        else:
            request.session['reference_from'] = 'direct'
    c = Context(
        Dict
    )
    response = HttpResponse(tmpl.render(c))
    response['Cache-Control'] = 'max-age=0'

    return response


def http_tmpl_context(request, tmpl, Dict):
    if not request.user.is_authenticated():
        Dict["is_user"] = False
    else:
        Dict["is_user"] = True
        Dict["username"] = request.user.username
        Dict = setup_user_menu(request.user, Dict)

    Dict["project_name"] = settings.PROJECT_NAME
    Dict["news_cats"] = main.models.Category.objects.all().order_by("ordering")
    Dict["pagetitle"] = my_messages.pagetitle_main
    Dict = setup_custom_meta(request, Dict)
    Dict["MEDIA_URL"] = settings.MEDIA_URL
    Dict["STATIC_URL"] = settings.STATIC_URL
    Dict["STATIC_SERVER"] = settings.STATIC_SERVER

    if not exclude_caching(request.get_full_path()):
        request.session['auth_user_path'] = request.get_full_path()

    Reference = request.GET.get('ref', False)
    if Reference:
        request.session['reference'] = Reference
        if request.META.has_key("HTTP_REFERER"):
            request.session['reference_from'] = request.META["HTTP_REFERER"]
        else:
            request.session['reference_from'] = 'direct'

    c = Context(Dict)
    response = HttpResponse(tmpl.render(c))
    response['Cache-Control'] = 'max-age=0'

    return response


def my_cached_paging(Id, ModelObjectTypre, CurrentPage=None, All=None, Pages=50):
    paginator = Paginator(All, Pages)
    AllPage = None
    try:
        AllPage = paginator.page(CurrentPage)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        AllPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        AllPage = paginator.page(paginator.num_pages)

    return AllPage


def http_json(Req, Dict):
    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'

    return Response


def json_false500(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = False
    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'
    Response.status_code = 500
    return Response


def json_false(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = False
    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'

    return Response


def json_denied(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = False
    Dict["description"] = ugettext("Permission denied for this page")

    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'

    return Response


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def json_true(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = True
    Response = HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'
    return Response


def tornadocache_delete(key):
    Url = "http://127.0.0.1:8081/cache?do=del&key=" + key
    try:
        urllib2.urlopen(Url, timeout=5)
    except:
        pass


def denied(Req, Dict=None):
    if Dict is None:
        Dict = {}
    t = loader.get_template("denied.html")
    Dict["denied_msg"] = ugettext("Permission denied for this page")
    return http_tmpl_context(Req, t, Dict)


def setup_custom_meta(req, NewContext):
    Path = req.get_full_path()
    try:
        custom_meta = main.models.CustomMeta.objects.get(url=Path)
        NewContext["pagetitle"] = custom_meta.title
        NewContext["description"] = custom_meta.meta_description
        NewContext["keywords"] = custom_meta.meta_keyword
        return NewContext
    except:
        return NewContext


def login_page_with_redirect(Req):
    t = loader.get_template("login_page4page.html")
    Dict = {"post_url": Req.get_full_path()}
    return http_tmpl_context(Req, t, Dict)


def get_crypto_object(Key, Iv=None):
    if Iv is None:
        Iv = Random.get_random_bytes(16)
    else:
        Iv = base64.b32decode(Iv)

    return ( AES.new(Key, AES.MODE_CBC, Iv), base64.b32encode(Iv) )


def common_encrypt(obj, value):
    str_value = str(value)
    AddLen = len(str_value) % 16
    tocrypt = str_value + " " * (16 - AddLen)
    print "%s %i" % (tocrypt, len(tocrypt))
    return base64.b32encode(obj.encrypt(tocrypt))


def common_decrypt(obj, value):
    return obj.decrypt(base64.b32decode(value)).strip()
