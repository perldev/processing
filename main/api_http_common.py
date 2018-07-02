# -*- coding: utf-8 -*-
import crypton.http 
from django.utils.translation import ugettext
from django.template import Context, loader
from django.core.cache import get_cache

import logging
import main.models
import json
from crypton import settings
from crypton import my_messages
import hashlib
import random


# def makebold(fn):
#def wrapped():
#return "<b>" + fn() + "</b>"
#return wrapped

#def makeitalic(fn):
#def wrapped():HttpResponse
#return "<i>" + fn() + "</i>"
#return wrapped

#@makebold
#@makeitalic
#def hello():
#return "hello habr"

#print hello() ## выведет <b><i>hello habr</i></b>




class AuthError(Exception):
    def __init__(self):
        self.value = "auth error"

    def __str__(self):
        return repr(self.value)


### TODO move this to cache
## PRIVATE FUNCTION
def check_api_sign(PublicKey, Sign, Body):
    # TODO move to cache
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
            if not Req.user: # or not Req.user.is_active:
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
                cache.set("nonce_" + PublicKey, Nonce)

            Req.user = check_api_sign(PublicKey, Sign, Req.body)
        except AuthError as e:
            return json_false500(Req, {"auth": False})
        except:
            return json_false500(Req, {"description": "some common"})
        return func2decorate(*args)

    return wrapper


def caching():
    return get_cache('default')

def my_cache(livetime=settings.CACHES['default']["TIMEOUT"]):
    def decorator(func2decorate):
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
            cache.set(CachedKey, RespJ, livetime)
            return cached_json_object(RespJ)
        return wrapper
        
    return decorator


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
    Response =  crypton.http.HttpResponse(json.JSONEncoder().encode({"status": False}))
    Response['Content-Type'] = 'application/json'
    return Response


def cached_json_object(RespJ):
    Response =  crypton.http.HttpResponse(RespJ)
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'
    return Response


##exports http_tmpl_context, http_json, json_false, json_denied, json_true, denied, setup_custom_meta, setup_user_menu

def get_memory_var(NameVal):
    try:
        Var = main.models.VolatileConsts.objects.get(Name=NameVal)
        return Var.Value
    except:
        return ""


def generate_key_from2(Val, Salt):
    m = hashlib.sha256()
    m.update(Val + Salt)
    return m.hexdigest()


def generate_key_from(Val, Salt):
    m = hashlib.sha256()
    m.update(Salt + Val)
    return m.hexdigest()


def generate_key(Salt=""):
    m = hashlib.sha256()
    m.update(Salt + str(random.randrange(1, 1000000000000000000)))
    return m.hexdigest()


def json_false500(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = False
    Response =  crypton.http.HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'
    Response.status_code = 500
    return Response


def json_false(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = False
    Response =  crypton.http.HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'

    return Response


def json_denied(Req, Dict=None):
    if Dict is None:
        Dict = {}
    Dict["status"] = False
    Dict["description"] = ugettext("Permission denied for this page")

    Response =  crypton.http.HttpResponse(json.JSONEncoder().encode(Dict))
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
    Response =  crypton.http.HttpResponse(json.JSONEncoder().encode(Dict))
    Response['Content-Type'] = 'application/json'
    Response['Cache-Control'] = 'max-age=0'
    return Response


def common_encrypt(obj, value):
    str_value = str(value)
    AddLen = len(str_value) % 16
    tocrypt = str(d) + " " * (16 - AddLen)
    return base64.b32encode(obj.encrypt(tocrypt))


def common_decrypt(obj, value):
    return obj.decrypt(base64.b32decode(value)).strip()
