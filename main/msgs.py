# -*- coding: utf-8 -*-

from django.http import HttpResponse
from crypton import settings
from django.core.mail import send_mail as send_django_mail
from  main.http_common import denied, http_tmpl_context, json_true, json_denied, http_json, caching, my_cached_paging, \
    tornadocache_delete
import main.models
from django.contrib.auth.models import User
from django.utils.translation import ugettext
from django.template import loader
import json

from django.core.mail import EmailMultiAlternatives
import threading


class EmailThreadHtml(threading.Thread):
    def __init__(self, subject, body, from_email, recipient_list, fail_silently, html):
        self.subject = subject
        self.body = body
        self.recipient_list = recipient_list
        self.from_email = from_email
        self.fail_silently = fail_silently
        self.html = html
        threading.Thread.__init__(self)

    def run(self):
        msg = EmailMultiAlternatives(self.subject, self.body, self.from_email, self.recipient_list)
        if self.html:
            msg.attach_alternative(self.html, "text/html")
        msg.send(self.fail_silently)


class EmailThreadText(threading.Thread):
    def __init__(self, subject, body, from_email, recipient_list, fail_silently, text):
        self.subject = subject
        self.body = body
        self.recipient_list = recipient_list
        self.from_email = from_email
        self.fail_silently = fail_silently
        threading.Thread.__init__(self)

    def run(self):
        main.models.AsyncMail(subject_mail=self.subject,
                              body=self.body,
                              to=self.recipient_list,
                              from_email=self.from_email,
                              is_html=False ).save()

 #       send_django_mail(self.subject, self.body, self.from_email, self.recipient_list, self.fail_silently)


def send_mail(subject, body, recipient_list, from_email=settings.DEFAULT_FROM_EMAIL,
              fail_silently=False, html=None, *args, **kwargs):
    EmailThreadText(subject, body, from_email, recipient_list, fail_silently, html).start()


def notify_me(Msg):
        send_mail(u'BTC TRADE UA',
                  Msg,
                  [ settings.EMAIL_ADMIN ],
                  fail_silently = False)

def notification(Req):
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        t = loader.get_template("notify.html")
        Dict = {}
        tornadocache_delete("balance_" + str(Req.user.id))
        List = list(main.models.Msg.objects.filter(user_to=Req.user, user_from_id=1, user_hide_to="false"))
        page = Req.GET.get('page', 1)
        PageObject = my_cached_paging("notify_" + str(Req.user.id), main.models.Msg, page, List)
        Dict["msgs"] = PageObject.object_list
        Dict["paging"] = PageObject
        main.models.Msg.objects.filter(user_to=Req.user, user_from_id=1, user_hide_to="false").update(
            user_seen_to="true")
        return http_tmpl_context(Req, t, Dict)


def hide(Req, Id):
    if not Req.user.is_authenticated():
        return json_denied(Req)
    else:
        MyMsg = main.models.Msg.objects.get(id=int(Id))
        if MyMsg.user_from == Req.user:
            MyMsg.user_hide_from = "true"
            MyMsg.save()
            return json_true(Req)

        if MyMsg.user_to == Req.user:
            MyMsg.user_hide_to = "true"
            MyMsg.save()
            return json_true(Req)

        return json_denied(Req)


def msgs_in(Req):
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        t = loader.get_template("msgs.html")
        Dict = {}
        List = list(main.models.Msg.objects.filter(user_to=Req.user, user_hide_to="false").exclude(user_from_id=1))
        Dict["msg_in_count"] = len(List)
        Dict["msg_out_count"] = main.models.Msg.objects.filter(user_from=Req.user, user_hide_from="false").exclude(
            user_to_id=1).count()

        Dict["is_msg_in"] = True
        page = Req.GET.get('page', 1)
        PageObject = my_cached_paging("msgs_in_" + str(Req.user.id), main.models.Msg, page, List)
        Dict["msgs"] = PageObject.object_list
        Dict["paging"] = PageObject

        main.models.Msg.objects.filter(user_to=Req.user, user_hide_to="false").update(user_seen_to="true")
        return http_tmpl_context(Req, t, Dict)


def msgs_out(Req):
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        t = loader.get_template("msgs.html")
        Dict = {}
        List = list(main.models.Msg.objects.filter(user_from=Req.user, user_hide_from="false").exclude(user_to_id=1))

        Dict["is_msg_in"] = False

        page = Req.GET.get('page', 1)
        PageObject = my_cached_paging("msgs_in_" + str(Req.user.id), main.models.Msg, page, List)
        Dict["msgs"] = PageObject.object_list
        Dict["paging"] = PageObject

        main.models.Msg.objects.filter(user_from=Req.user, user_hide_from="false").update(user_seen_from="true")
        Dict["msg_in_count"] = main.models.Msg.objects.filter(user_to=Req.user, user_hide_to="false").exclude(
            user_from_id=1).count()
        Dict["msg_out_count"] = len(List)
        return http_tmpl_context(Req, t, Dict)


def create(Req):
    if not Req.user.is_authenticated():
        return denied(Req)
    else:
        if cache.get("cryptonbanned_" + Req.user.username, False):
            return denied(Req)

        Username = Req.REQUEST.get('whom', None)
        Msg = Req.REQUEST.get('msg', None)
        if Msg is None:
            return http_json(Req, {'status': False, "description": ugettext("Fill fields correctly")})

        if Username is None:
            return http_json(Req, {'status': False, "description": ugettext("Fill fields correctly")})
        if Username == Req.user.username:
            return http_json(Req, {'status': False, "description": ugettext("Sender and reciver the same user")})

        try:
            To = User.objects.get(username=Username)
            msg(Msg, Req.user, To)
        except User.DoesNotExist:
            return http_json(Req, {'status': False, "description": ugettext("We can't find reciver of the message")})

        return json_true(Req)


def system_notify(MsgText, To):
    msg = None
    if isinstance(To, int) or isinstance(11L, long):
        msg = main.models.Msg(user_from_id=1, user_to_id=To, text=MsgText)
    else:
        msg = main.models.Msg(user_from_id=1, user_to=To, text=MsgText)

    msg.save()
    return True


def msg(MsgText, From, To):
    msg = main.models.Msg(user_from=From, user_seen_from="true", user_to=To, text=MsgText)
    msg.save()
    return True


def notify_email_admin(Req, Type):
    pass


def notify_email(User, Type, Obj):

    try:
        Setting = main.models.UserCustomSettings.objects.get(user=User, setting__title=Type)
    except:
        return True

    if Setting.value == "no":
        return True
    else:
        if Type == "auth_notify":
            auth_notify(User, Obj)
        if Type == "deposit_notify":
            deposit_notify(User, Obj)
        if Type == "withdraw_notify":
            withdraw_notify(User, Obj)


def deposit_notify(user, Obj):
    if isinstance(Obj, main.models.CryptoTransfers):
        send_mail(u'Зачисление средств на ' + settings.BASE_HOST,
                  deposit_notify_msg_crypto(user, Obj),
                  [user.email],
                  fail_silently=True)
        return True

    if isinstance(Obj, main.models.LiqPayTrans):
        send_mail(u'Зачисление средств на ' + settings.BASE_HOST,
                  deposit_notify_msg_liqpay(user, Obj),
                  [user.email],
                  fail_silently=True)
        return True

    send_mail(u'Зачисление средств на ' + settings.BASE_HOST,
              deposit_notify_msg_p24(user, Obj),
              [user.email],
              fail_silently=True)

    return True


def withdraw_notify(user, Obj):
    if isinstance(Obj, main.models.CryptoTransfers):
        send_mail(u'Вывод средств с ' + settings.BASE_HOST,
                  withdraw_notify_msg_crypto(user, Obj),
                  [user.email],
                  fail_silently=True)

        return True
    if isinstance(Obj, main.models.CardP2PTransfers):
        send_mail(u'Вывод средств  с' + settings.BASE_HOST,
                  withdraw_notify_msg_p2p(user, Obj),
                  [user.email],
                  fail_silently=True)

        return True


def auth_notify(user, Req):
    send_mail(u'Авторизация на  ' + settings.BASE_HOST,
              auth_notify_msg(user, Req),
              [user.email],
              fail_silently=False)

# TODO localization in notify messages
# вопрос локализации тут
def withdraw_notify_msg_p2p(user, P2P):
    return u"Выведены  средства на карту \n\
Сумма: %s %s\n\
Карта получателя: %s\n\
На имя: %s\n\
Пользователь: %s\n\
\n\n\n\
С уважением служба поддержки %s\n\
" % ( str(P2P.amnt), str(P2P.currency), P2P.CardNumber, P2P.CardName, 
      user.username, settings.PROJECT_NAME )


def withdraw_notify_msg_crypto(user, Crypto):
    return u"Выведены  средства \n\
Сумма: %s %s\n\
Получатель: %s\n\
Пользователь: %s\n\
\n\n\n\
С уважением служба поддержки %s\n\
" % (str(Crypto.amnt), str(Crypto.currency),
     Crypto.account, user.username, settings.PROJECT_NAME )


def deposit_notify_msg_p24(user, DebP24):
    return u"Зачисление средств \n\
Сумма: %s %s\n\
Пользователь: %s\n\
\n\n\n\
С уважением служба поддержки %s\n\
" % (str(DebP24.amnt), str(DebP24.currency.title),
     user.username, settings.PROJECT_NAME )


def deposit_notify_msg_liqpay(user, DebCredLiqPay):
    return u"Зачисление средств \n\
Сумма: %s %s\n\
LiqPay пользователь: %s\n\
Пользователь: %s\n\
\n\n\n\
С уважением служба поддержки %s\n\
" % (str(DebCredLiqPay.amnt), str(DebCredLiqPay.currency.title),
    DebCredLiqPay.phone, user.username, settings.PROJECT_NAME )


def deposit_notify_msg_crypto(user, Crypto):
    return u"Зачисление средств \n\
Сумма: %s %s\n\
Отправитель: %s\n\
Пользователь: %s\n\
\n\n\n\
С уважением служба поддержки %s\n\
" % (str(Crypto.amnt), str(Crypto.currency), 
    Crypto.account, user.username, settings.PROJECT_NAME )


def pins_reset_email(i, Key):
    send_mail(u'Смена  PIN-кода ' + settings.BASE_HOST,
              pin_email(i, Key),
              [i.user.email],
              fail_silently=False)


def pin_email(item, Key):
    return u"Смена PIN-кода  \n\
Ваш  PIN код доступен по ссылке  %s\n\
Ссылка действительна 48 часа\n\
Пожайлуста сохраниет ваш PIN код в надежном месте, и удалите это сообщение\n\
как можно скорее.\n\
Так же вместо PIN-кода вы можете пользоваться двухфакторной авторизацией - \n\
Ее настроить вы можете теперь в своем профиле\n\
\n\
\n\
С уважением служба поддержки %s\n\
" % (settings.BASE_URL + "pin_image_page/" + str(Key), settings.PROJECT_NAME  )


def auth_notify_msg(user, Req):
    if Req.result_auth == "bad":
        return u"Неудачная попытка авторизации \n\
IP : %s\n\
Пользователь : %s\n\
С уважением служба поддержки %s\n\
" % (Req.META['REMOTE_ADDR'], user.username, settings.PROJECT_NAME)
    else:
        return u"Удачная попытка авторизации \n\
IP : %s\n\
Пользователь : %s\n\
С уважением служба поддержки %s\n\
" % (Req.META['REMOTE_ADDR'], user.username, settings.PROJECT_NAME)


def notify_admin_withdraw_fail(Item, State):
    if isinstance(Item, main.models.CardP2PTransfers):
        try:
            send_mail(u'Неудачный вывод  ' + settings.BASE_HOST,
                      fail_p24_withdraw(Item, State),
                      [settings.ADMIN_COPY],
                      fail_silently=False)
        except:
            pass


def fail_p24_withdraw(P2P, State):
    return u"Неудачная попытка выведения  средства на карту \n\
Сумма: %s %s\n\
Карта получателя: %s\n\
На имя: %s\n\
Пользователь: %s\n\
Result:\n\
\n\
%s\n\
\n\
\n\n\n\
С уважением служба поддержки %s\n\
" % ( str(P2P.amnt), str(P2P.currency), P2P.CardNumber, P2P.CardName, 
       P2P.user.username, State, settings.PROJECT_NAME )  
        
