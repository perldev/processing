# -*- coding: utf-8 -*-
from crypton import my_messages
from django.utils.translation import ugettext as _
from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse
from crypton import settings
from crypton import my_messages
import main.msgs

from main.http_common import http_tmpl_context, http_json, json_false, json_denied, json_true, denied
from main.http_common import setup_user_menu, generate_key_from
from main.http_common import generate_key, caching, get_memory_var, json_false500, json_auth_required
from main.http_common import format_numbers_strong, format_numbers4

from django.shortcuts import redirect
from main.user_forms import UsersForgotLinkPswd, UsersForgotMail
from django.contrib.auth.models import User
from main.models import HoldsWithdraw
from main.models import ResetPwdLink

from sdk.g2f import auth

from django.views.decorators.cache import cache_page
from datetime import datetime
import hashlib
import random
import json
from decimal import Decimal, getcontext
from main.models import dictfetchall, store_registration
import crypton.settings


__author__ = 'bogdan'


def reset_pwd_mail(User, SessionKey):
    Url = crypton.settings.BASE_URL + "reset_pwd/" + SessionKey
    return _(u"Вы заказали обновление пароля на {name}\n\
Данные для входа : \n\
Имя пользователя: \"{username}\" \n \
Перейдите пожайлуста по ссылке для завершения процедуры обновления: {url} \n\
\n\n\n\
С уважением служба поддержки {project_name}\n\
                ").format(name=crypton.settings.PROJECT_NAME, username=User.username, url=Url,
                          project_name=settings.PROJECT_NAME)


def forgot(Req):
    t = loader.get_template("simple_form_center.html")
    Dict = {}
    Dict["title"] = settings.secondary_main_forgot
    forgotForm = UsersForgotMail()
    Dict["form"] = forgotForm.as_p()
    Dict["common_help_text"] = settings.common_help_text
    Dict["action"] = "/forgot_action"
    Dict["action_title"] = settings.reset_password_title
    return http_tmpl_context(Req, t, Dict)


def forgot_action(request):
    Form = UsersForgotMail(request.POST)
    Dict = {}
    if Form.is_valid():
        # Save a new Article object from the form's data.

        SessionLink = generate_key("hold")[10:30]
        reset_link = ResetPwdLink(user=Form.user, key=SessionLink)
        reset_link.save()
        # if settings.DEBUG is False:
        Email = Form.cleaned_data["email"]

        main.msgs.send_mail(_(u'Обновление пароля на бирже ' + settings.BASE_HOST),
                            reset_pwd_mail(Form.user, SessionLink),
                            [Email],
                            fail_silently=False)

        return redirect("/forgot_success")
    else:
        t = loader.get_template("simple_form_center.html")
        Dict["title"] = settings.secondary_main_forgot
        Dict["form"] = Form.as_p()
        Dict["common_help_text"] = settings.common_help_text
        Dict["action"] = "/forgot_action"
        Dict["action_title"] = settings.reset_password_title
        return http_tmpl_context(request, t, Dict)


def forgot_success(Req):
    t = loader.get_template("simple_msg_center.html")
    Dict = {}
    Dict["title"] = my_messages.secondary_main_forgot
    Dict["simple_msg"] = my_messages.forgot_sending_email_msg
    return http_tmpl_context(Req, t, Dict)


def reset_pwd(request, Key):
    Form = UsersForgotLinkPswd()
    try:
        link = ResetPwdLink.objects.get(key=Key, status="created")
        Dict = {}
        Dict["title"] = my_messages.secondary_main_forgot_link
        Dict["form"] = Form.as_p()
        Dict["common_help_text"] = my_messages.forgot_main_help_text
        Dict["action"] = "/reset_pwd_action/" + Key
        Dict["action_title"] = my_messages.forgot_main_update
        t = loader.get_template("simple_form_center.html")
        return http_tmpl_context(request, t, Dict)
    except ResetPwdLink.DoesNotExist:
        return redirect("/reset_link_no_found")


def reset_pwd_action(request, Key):
    link = None
    try:
        link = ResetPwdLink.objects.get(key=Key, status="created")
    except:
        return redirect("/reset_link_no_found")
    Form = UsersForgotLinkPswd(request.POST)
    Dict = {}
    if Form.is_valid():
        link.status = 'processed'
        passwd = Form.cleaned_data["password1"]
        link.user.set_password(passwd)
        link.user.save()
        link.save()
        return redirect("/reset_success")
    else:
        t = loader.get_template("simple_form_center.html")
        Dict["title"] = my_messages.secondary_main_forgot_link
        Dict["form"] = Form.as_p()
        Dict["common_help_text"] = my_messages.forgot_main_help_text
        Dict["action"] = "/reset_pwd_action/" + Key
        Dict["action_title"] = my_messages.forgot_main_update
        return http_tmpl_context(request, t, Dict)


def reset_success(Req):
    t = loader.get_template("simple_msg_center.html")
    Dict = {}
    Dict["title"] = my_messages.secondary_main_forgot_link
    Dict["simple_msg"] = my_messages.reset_pwd_success
    return http_tmpl_context(Req, t, Dict)


def reset_link_no_found(Req):
    t = loader.get_template("simple_msg_center.html")
    Dict = {}
    Dict["title"] = my_messages.secondary_main_forgot_link
    Dict["simple_msg"] = my_messages.forgot_link_not_found_msg
    return http_tmpl_context(Req, t, Dict)
