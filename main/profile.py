# -*- coding: utf-8 -*-

# Create your views here.
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from crypton import settings
from django.core.mail import send_mail
from django.utils.translation import ugettext
import crypton.my_messages
from django.db import connection
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.models import User
from main.models import Accounts, Currency, ActiveLink, TradePairs, Orders, Msg, StaticPage, HoldsWithdraw, CustomMeta, \
    ApiKeys
from main.models import UserCustomSettings, CustomSettings, HoldsWithdraw
from main.models import PinsImages
from main.forgot_password_views import reset_pwd_mail
import hashlib
import random
import json
from decimal import Decimal, getcontext
import urllib2
from main.http_common import http_tmpl_context, json_denied, json_true, setup_user_menu, denied, generate_key_from, \
    json_false500, format_numbers4
from main.models import dictfetchall
from main.http_common import generate_key, json_auth_required, g2a_required, start_show_pin, auth_required_with_login
from main.user_forms import PinChangeForm
from main.finance_forms import PinForm
from sdk.image_utils import ImageText, draw_text, pin
import sdk.g2f as g2f
from main.http_common import caching
import os


def user_settings(Req, Name, Value):
    if not Req.user.is_authenticated():
        return json_denied(Req, {"ru_description": u"Для изменения персональных настроек пожайлуста авторизируйтесь"})

    if Value == "yes":
        Value = "yes"
    else:
        Value = "no"

    Setting = None
    try:
        Setting = CustomSettings.objects.get(title=Name)
        Object = UserCustomSettings.objects.get(user=Req.user, setting=Setting)
        Object.value = Value
        Object.save()
        return json_true(Req)
    except UserCustomSettings.DoesNotExist:
        obj = UserCustomSettings(user=Req.user, setting=Setting, value=Value)
        obj.save()
        return json_true(Req)
        # except:
        #return json_denied(Req, {"ru_description": u"Не удалось поменять"} )


def pin_change(Req):
    if not Req.user.is_authenticated():
        return denied(Req)

    t = loader.get_template("pin_form_working.html")
    Form = PinChangeForm(user=Req.user)
    Dict = {}
    Dict["title"] = crypton.my_messages.pin_reset_form_title
    Dict["form"] = Form.as_p()
    Dict["action"] = "/profile/pin_change_do"
    Dict["action_title"] = settings.pin_change_title
    Dict["pin_load"] = True
    return http_tmpl_context(Req, t, Dict)


def pin_change_do(Req):
    if not Req.user.is_authenticated():
        return denied(Req)

    Form = PinChangeForm(Req.POST, user=Req.user)
    Dict = {}

    if Form.is_valid():
        pin_name = settings.ROOT_PATH + "pins_images/pin_%i.png" % (Req.user.id)
        (Letters, Value) = pin(pin_name)
        i = None
        try:
            i = PinsImages.objects.get(user=Req.user)
        except PinsImages.DoesNotExist:
            i = PinsImages(user=Req.user,
                           img=pin_name
            )

        i.req_vocabulary = Letters
        i.hash_value = generate_key_from(Value, settings.PIN_SALT)
        i.operator = Req.user
        i.status = "created"
        i.save()
        ##устанавливаем холд на вывод
        Key = start_show_pin(Req.user.id, 160000)
        return redirect("/pin_image_page/%s" % (Key))
    else:
        t = loader.get_template("simple_form.html")
        Dict = {}
        Dict["form"] = Form.as_p()
        Dict["action"] = "/profile/pin_change_do"
        Dict["action_title"] = settings.pin_change_title
        Dict["pin_load"] = True
        return http_tmpl_context(Req, t, Dict)


# DEPRECATED
def reset(Req):
    if not Req.user.is_authenticated():
        return denied(Req)

    hold = HoldsWithdraw(user=Req.user, hours=settings.default_hold)
    hold.save()
    NewPwd = generate_key("hold")[10:30]
    # if settings.DEBUG is False:
    Email = Req.user.email
    send_mail(u'Обновление пароля на сайте ' + settings.BASE_HOST,
              reset_pwd_mail(Req.user, NewPwd),
              [Email],
              fail_silently=False)

    Req.user.set_password(NewPwd)
    Req.user.save()
    return json_true(Req)


##IT COULD BE a bottle neck


@json_auth_required
@g2a_required
def g2a_turn_off(request):
    print request.session['use_f2a']
    setting = UserCustomSettings.objects.get(user=request.user, setting__title="g2a")
    setting.value = "no"
    setting.save()
    request.session['use_f2a'] = False
    return json_true(request)


@json_auth_required
def g2a_qr(request):
    key = request.REQUEST.get('key')
    cache = caching()
    Secret = cache.get("temp_qr" + key, False)
    if not Secret:
        return json_false500(request)

    valid_image = settings.ROOT_PATH + "qr_images/qr_%i.png" % (Secret)
    with open(valid_image, "rb") as f:
        Response = HttpResponse(f.read(), mimetype="image/png")
        Response['Cache-Control'] = 'max-age=0'
        return Response


@json_auth_required
def setup_g2a_verify(request, val):
    CachedKey = 'qr_' + str(request.user.id)
    cache = caching()
    Secret = cache.get(CachedKey, False)

    if not Secret:
        return json_false500(request)

    if g2f.auth(Secret, val):

        Setting = None
        SettingType = CustomSettings.objects.get(title="g2a")
        try:
            Setting = UserCustomSettings.objects.get(user=request.user, setting=SettingType)
        except UserCustomSettings.DoesNotExist:
            Setting = UserCustomSettings(user=request.user,
                                         setting=SettingType,
                                         value=SettingType.def_value)

        valid_image = settings.ROOT_PATH + "qr_images/qr_%i.png" % (request.user.id)
        os.remove(valid_image)
        Setting.value = Secret
        Setting.save()
        request.session['use_f2a'] = True
        return json_true(request)
    else:
        return json_false500(request)


@json_auth_required
def setup_g2a(request):
    CachedKey = 'qr_' + str(request.user.id)
    cache = caching()

    Dict = {}
    (base32, base16) = g2f.newSecret()
    Link = g2f.getQRLink(request.user.username, base32)
    imgRequest = urllib2.Request(Link)

    imgData = urllib2.urlopen(imgRequest).read()
    valid_image = settings.ROOT_PATH + "qr_images/qr_%i.png" % (request.user.id)
    F = open(valid_image, 'wb')
    F.write(imgData)
    F.close()

    Dict["g2a_private_key32"] = base32
    Dict["g2a_private_key"] = base16

    temp_qr = generate_key("qr")
    Dict["g2a_qr"] = "/profile/qr?key=%s" % ( temp_qr )

    cache.set("temp_qr" + temp_qr, request.user.id, 300)
    cache.set(CachedKey, base32, 600)

    return json_true(request, Dict)


@auth_required_with_login
def pin_image_page(request, Key):
    Dict = {}
    t = loader.get_template("pin_page.html")
    Dict["title"] = settings.pin_page
    Dict["pin"] = Key
    return http_tmpl_context(request, t, Dict)


@json_auth_required
def pin_image(request, Key):
    cache = caching()
    CachedKey = "pin_" + Key

    UserId = cache.get(CachedKey, False)
    if int(request.user.id) != int(UserId):
        return denied(request)
    Pin = PinsImages.objects.get(user_id=int(UserId))
    valid_image = settings.ROOT_PATH + "pins_images/pin_%i.png" % ( int(UserId) )
    with open(valid_image, "rb") as f:
        Response = HttpResponse(f.read(), mimetype="image/png")
        Response['Cache-Control'] = 'max-age=0'
        return Response


def user_private_key(Req):
    Res = ApiKeys.objects.get(user=Req.user)
    Dict = {}
    t = loader.get_template("ajax_simple_msg.html")
    Dict = {}
    Dict["title"] = "Private API Key"
    Dict["simple_msg"] = Res.private_key
    return http_tmpl_context(Req, t, Dict)


@auth_required_with_login
@g2a_required
def private_key(Req):
    Use2fa = False
    if Req.session.has_key("use_f2a"):
        Use2fa = Req.session["use_f2a"]

    if not Use2fa:
        Form = PinForm(Req.POST, user=Req.user)
        if Form.is_valid():
            return user_private_key(Req)
        else:
            return json_false500(Req)
    else:
        return user_private_key(Req)


@auth_required_with_login
def page_private_key(Req):
    Use = False
    if Req.session.has_key("use_f2a"):
        Use = Req.session["use_f2a"]

    t = loader.get_template("common_secure_page_api.html")
    Dict = {}
    Dict["type"] = "show_privat_key"
    Dict["key"] = generate_key()
    Dict["pin_load"] = not Use
    Dict["use_f2a"] = Use
    return http_tmpl_context(Req, t, Dict)


def profile(request, UserName):
    if not request.user.is_authenticated():
        return denied(request)

    Dict = {}

    for setting in UserCustomSettings.objects.filter(user=request.user):
        if setting.value != "no":
            Dict[setting.setting.title] = True
            Dict[setting.setting.title + "_value"] = setting.value

    if request.user.username == UserName:
        t = loader.get_template("profile.html")
        Dict = setup_user_menu(request.user, Dict)
        Class = UserCustomSettings.objects.get(user=request.user, setting__title="class")
        Identity = UserCustomSettings.objects.get(user=request.user, setting__title="identity")
        Res = ApiKeys.objects.get(user=request.user)
        Dict["public_key_api"] = Res.public_key
        Dict["class_value"] = Class.value
        Dict["identity_value"] = Identity.value
        DealComis = format_numbers4(Decimal(Dict["deal_comission_value"]) * Decimal("100"))
        request.session["deal_comission_show"] = DealComis
        request.session["deal_comission"] = format_numbers4(Decimal(Dict["deal_comission_value"]))
        Dict["deal_comission_value"] = DealComis

        Dict["is_own_profile"] = True
        Dict["client"] = request.user
        return http_tmpl_context(request, t, Dict)
    else:
        t = loader.get_template("profile.html")
        Dict = setup_user_menu(request.user)
        try:
            usr = User.objects.get(username=UserName)
            Class = UserCustomSettings.objects.get(user=usr, setting__title="class")
            Dict["client"] = usr
            Dict["class_value"] = Class.value

        except:
            return denied(request)

        Dict["is_own_profile"] = False

        return http_tmpl_context(request, t, Dict)
  
