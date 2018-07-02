# -*- coding: utf-8 -*-
from django.core.mail import get_connection, EmailMultiAlternatives
from django.db import models
from django.contrib import admin
from crypton import settings
from django import forms
from django.db import connection
from django.core.cache import get_cache

from django.contrib.auth.models import User
from django.utils.html import strip_tags
from main.msgs import notify_email, pins_reset_email, notify_admin_withdraw_fail
from main.http_common import generate_key_from, start_show_pin, delete_show_pin, generate_key, generate_key_from2, \
    format_numbers10, format_numbers_strong
from django.db import connection
#from sdk.image_utils import ImageText, draw_text, pin
from decimal import Decimal
from main.subscribing import subscribe_connection
from datetime import datetime
from django.utils import timezone

import math
#from Crypto.Cipher import AES
from django.db import transaction
import base64
from sdk.crypto import CryptoAccount
import main.http_common
from main.account import get_account
import main.account
from django.core.urlresolvers import reverse


# Create your models here.
DEBIT_CREDIT = (
    ("in", u"debit"),
    ("out", u"credit"),
)

BOOL = (
    ("true", u"true"),
    ("false", u"false"),
)

STATUS_ORDER = (
    ("manually", u"ручная"),
    ("deposit", u"депозит"),
    ("withdraw", u"вывод"),
    ("bonus", u"партнерское вознаграждение"),
    ("payin", u"пополнение"),
    ("comission", u"коммиссионные"),
    ("created", u"создан"),
    ("incifition_funds", u"недостаточно средств"),
    ("currency_core", u"валюты счетов не совпадают"),
    ("processing", u'в работе'),
    ("processing2", u'в работе 2'),
    ("canceled", u'отменен'),
    ("wait_secure", u'ручная обработка'),
    ("order_cancel", u"отмена заявки"),
    ("deal", u"сделка"),
    ("auto", u"автомат"),
    ("automanually", u"мануальный автомат"),
    ("deal_return", u"возврат маленького остатка"),
    ("processed", u'исполнен'),
    ("core_error", u'ошибка ядра'),
)


def checksum(Obj):
    return True





class PartnershipAdmin(admin.ModelAdmin):
    list_display = ['user_ref', 'user', 'url_from', 'income', 'income_from', 'status']


class Partnership(models.Model):
    user_ref = models.ForeignKey(User, verbose_name=u"Клиент", related_name="partner")
    user = models.ForeignKey(User, verbose_name=u"Приведенный клиент", related_name="join_by_parnter")
    url_from = models.CharField(verbose_name=u"URL from", max_length=255, default="direct")
    income = models.CharField(verbose_name=u"доход", max_length=255, default="0")
    income_from = models.DateTimeField(verbose_name=u"Дата пересчета", editable=False)
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', editable=False)

    class Meta:
        verbose_name = u'Референс'
        verbose_name_plural = u'Референсы'


def get_decrypted_user_pin(user):
    item = PinsImages.objects.using("security").get(user_id=user.id)
    (Obj, Iv) = main.http_common.get_crypto_object(settings.CRYPTO_KEY, item.iv_key)
    return common_decrypt(Obj, item.raw_value)


def store_registration(UserName, Email, Password, Reference=False, From=False):
    new_user = User.objects.create_user(UserName, Email, Password)

    new_user.is_active = False
    new_user.save()

    if Reference:
        Object = UserCustomSettings.objects.get(value=Reference, setting__title="partners")

        CreatePartnership = None
        if From:
            CreatePartnership = Partnership(user_ref=Object.user, user=new_user, url_from=From)
        else:
            CreatePartnership = Partnership(user_ref=Object.user, user=new_user)

        CreatePartnership.save()

    hold = HoldsWithdraw(user=new_user, hours=0)
    hold.save()
    ListCurrency = Currency.objects.all()
    for i in ListCurrency:
        new_account = Accounts(user=new_user, currency=i, balance=0)
        new_account.save()

    bulk_add = []
    for setting in CustomSettings.objects.all():
        if setting.title == "partners":
            setting.def_value = new_user.id
        bulk_add.append(
            UserCustomSettings(user=new_user,
                               value=setting.def_value,
                               setting=setting
            )
        )
    UserCustomSettings.objects.bulk_create(bulk_add)
    rand_key = generate_key()
    f = ActiveLink(user=new_user, key=rand_key)
    f.save()
    return (new_user, rand_key)


class TransError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class OrderTimerAdmin(admin.ModelAdmin):
    list_display = ['order', 'time_work']


class OrderTimer(models.Model):
    order = models.IntegerField(verbose_name=u"Ордер")
    time_work = models.DecimalField(max_digits=18,
                                    decimal_places=10,
                                    verbose_name=u"Время",
                                    default=0)
    error = models.CharField(verbose_name=u"Error", null=True, default='', max_length=255)


    class Meta:
        verbose_name = u'Временной замер'
        verbose_name_plural = u'Временные замеры'


class ApiKeys(models.Model):
    public_key = models.CharField(verbose_name=u"Публичный ключ", max_length=255)
    private_key = models.CharField(verbose_name=u"Приватный ключ", max_length=255)
    user = models.ForeignKey(User, verbose_name=u"Клиент")

    class Meta:
        verbose_name = u'API настроек пользователя'
        verbose_name_plural = u'API настроек пользователя'


def get_api_settings(PublicKey):
    return ApiKeys.objects.get(public_key=PublicKey)


class CustomSettings(models.Model):
    title = models.CharField(verbose_name=u"Название настройки", max_length=255)
    def_value = models.CharField(verbose_name=u"Значение по умолчанию", null=True, max_length=255)

    class Meta:
        verbose_name = u'Тип настроек пользователя'
        verbose_name_plural = u'Типы настроек пользователя'

    def __unicode__(obj):
        return obj.title


class CustomSettingsAdmin(admin.ModelAdmin):
    list_display = ['title']

    def save_model(self, request, obj, form, change):

        if obj.id is None:
            obj.save()
            bulk_add = []
            for item in User.objects.all():
                bulk_add.append(
                    UserCustomSettings(user=item,
                                       value=obj.def_value,
                                       setting=obj
                    )
                )
            UserCustomSettings.objects.bulk_create(bulk_add)

        else:
            obj.save()

        return True


# 6 2+4,3+3,4+2,5+1,1+5  = 1/36*5

# 8 6+2,2+6,4+4,3+5,5+3 = 1/36*5

#7 5+2,2+5,4+3,3+4  = 1/36*4

#9 5+4,6+3,4+5,3+6 = 1/36*4

#5 1+4,4+1,2+3,3+2 = 1/36*4

#4 2+2,3+1,1+3 = 3/36

#10 5+5,6+4,4+6 = 3/36

#11 5+6, 6+5 = 1/36*4

#12 6+6

#3 1+2,2+1

#2 1+1

class PersonalSigns(models.Model):
    user_id = models.IntegerField(verbose_name=u"Клиент")
    key = models.CharField(max_length=255, verbose_name=u"key")

    def __unicode__(o):
        return str(o.user_id)

    class Meta:
        verbose_name = u'Ключи пользователей'
        verbose_name_plural = u'Ключ пользователя'


def new_pin4user(obj, oper):
    pin_name = settings.ROOT_PATH + "pins_images/pin_%i.png" % (obj.user.id)
    (Letters, Value) = pin(pin_name)
    obj.req_vocabulary = Letters
    obj.hash_value = generate_key_from(Value, settings.PIN_SALT)
    obj.img = pin_name
    obj.status = "created"
    obj.raw_value = Value
    obj.operator = oper
    delete_show_pin(obj.show_key)
    Key = start_show_pin(obj.user.id, 160000)
    obj.show_key = Key
    obj.save()

    if obj.type_recover == "email":
        pins_reset_email(obj, Key)

    return obj.show_key


class PinsImagesAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', "operator", "status", "type_recover"]
    list_filter = ['user']
    actions = ['reset_pin']

    def reset_pin(self, request, queryset):
        for i in queryset:
            new_pin4user(i, request.user)

    def save_model(self, request, obj, form, change):

        if obj.id is None:
            new_pin4user(obj, request.user)

    reset_pin.short_description = u"Reset Pin"


class PinsImages(models.Model):
    hash_value = models.CharField(max_length=255, verbose_name=u"Hash", editable=False)
    req_vocabulary = models.CharField(max_length=55, verbose_name=u"Словарь", editable=False)
    raw_value = models.CharField(max_length=255, editable=False)
    show_key = models.CharField(max_length=255, editable=False, null=True, blank=True)
    img = models.ImageField(upload_to="pins_images",
                            verbose_name=u'Картинка', blank=True, null=True, editable=False)
    date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата старта", editable=False)
    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_pin")

    operator = models.ForeignKey(User, verbose_name=u"Оператор изменений",
                                 related_name="operator_pin",
                                 editable=False)

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', editable=False)
    RECOVER_ORDER = (
        ("email", u"email"),
        ("phone", u"телефон"),
        ("skype", u"skype"),
    )

    type_recover = models.CharField(max_length=40,
                                    choices=RECOVER_ORDER,
                                    default='email', editable=False)
    iv_key = models.CharField(max_length=255,
                              default='', editable=False)

    def __unicode__(o):
        return str(o.user)

    class Meta:
        verbose_name = u'Пин пользователя'
        verbose_name_plural = u'Пины пользователя'


class UserCustomSettings(models.Model):
    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_settings",
                             editable=False)
    setting = models.ForeignKey(CustomSettings, verbose_name=u"Настройки")
    value = models.CharField(max_length=255, verbose_name=u"Значение")
    value = models.CharField(max_length=255, verbose_name=u"Значение")
    value = models.CharField(max_length=255, verbose_name=u"Значение")

    class Meta:
        verbose_name = u'Настройки пользователей'
        verbose_name_plural = u'Настройки пользователя'


class UserCustomSettingsAdmin(admin.ModelAdmin):
    list_display = ["id", 'user', 'setting', "value"]
    list_filter = ('user', 'setting', "value")


#search_args = []
#for term in request.GET['query_term'].split():
#for query in ('first_name__istartswith', 'last_name__istartswith'):
#search_args.append(Q(**{query: term}))


#all_soggs = Entity.objects.filter(reduce(operator.or_, search_args))


class MyUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'is_staff']
    search_fields = ('username', 'email')
    actions = ['hold24', 'hold48', 'hold36', 'hold_week', "ban_chat_1h", "ban_chat_15m", "ban_chat_day", "ban_chat_3h",
               'unban_chat', 'reset_pin']

    def caching(self):
        return get_cache('default')

    def reset_pin(self, request, queryset):
        for i in queryset:
            obj = PinsImages.objects.get(user=i)
            new_pin4user(obj, request.user)

    def unban_chat(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.username, "banned", 1)


    def ban_chat_1h(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.username, "banned", 3600)

    def ban_chat_15m(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.username, "banned", 900)

    def ban_chat_day(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.username, "banned", 86000)

    def ban_chat_3h(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.username, "banned", 10800)


    def hold24(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i, hours=24)
            hold.save()

    def hold48(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i, hours=48)
            hold.save()

    def hold36(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i, hours=36)
            hold.save()

    def hold_week(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i, hours=140)
            hold.save()

            #do something ...

    hold24.short_description = u"Остановить вывод на 24 часа"
    hold_week.short_description = u"Остановить вывод на неделю"
    hold48.short_description = u"Остановить вывод на 48 часа"
    hold36.short_description = u"Остановить вывод на 36 часа"


def mines_prec(dec_number1, dec_number2, Prec):
    return Decimal(Decimal(dec_number1)-Decimal(dec_number2))
    PrecMul = 10 ** Prec
    PreStr = list(str(int(dec_number1 * PrecMul) - int(dec_number2 * PrecMul)))
    #print PreStr
    MinesAdd = False
    if PreStr[0] == '-':
        PreStr = PreStr[1:]
        MinesAdd = True

    size = len(PreStr)
    #print size
    if size > Prec:
        Dot = size - Prec
        if MinesAdd:
            return Decimal("-" + "".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
        return Decimal("".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
    else:

        Mask = ['0'] * Prec
        #print Mask
        From = Prec - size
        #print From
        Mask[From:] = PreStr
        #print Mask
        if MinesAdd:
            return Decimal("-0." + "".join(Mask))
        return Decimal("0." + "".join(Mask))


def plus_prec(dec_number1, dec_number2, Prec):
    return Decimal(dec_number1)+Decimal(dec_number2)
    PrecMul = 10 ** Prec
    PreStr = list(str(int(dec_number1 * PrecMul) + int(dec_number2 * PrecMul)))
    MinesAdd = False
    if PreStr[0] == '-':
        PreStr = PreStr[1:]
        MinesAdd = True
    size = len(PreStr)

    if size > Prec:
        Dot = size - Prec
        if MinesAdd:
            return Decimal('-' + "".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))

        return Decimal("".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
    else:
        Mask = ['0'] * Prec
        From = Prec - size
        Mask[From:] = PreStr
        if MinesAdd:
            return Decimal("-0." + "".join(Mask))
        return Decimal("0." + "".join(Mask))


def sato2Dec(Satochi):
    PreStr = list(str(int(Satochi)))
    size = len(PreStr)
    Prec = 8
    if size > Prec:
        Dot = size - Prec
        return Decimal("".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
    else:
        Mask = ['0'] * Prec
        From = Prec - size
        Mask[From:] = PreStr
        return Decimal("0." + "".join(Mask))


def to_prec(dec_number, Prec):
    PrecMul = 10 ** Prec
    PreStr = list(str(int(dec_number * PrecMul)))
    MinesAdd = False
    if PreStr[0] == '-':
        PreStr = PreStr[1:]
        MinesAdd = True

    size = len(PreStr)

    if size > Prec:
        Dot = size - Prec
        if MinesAdd:
            return Decimal('-' + "".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
        return Decimal("".join(PreStr[:Dot]) + "." + "".join(PreStr[Dot:]))
    else:
        Mask = ['0'] * Prec
        From = Prec - size
        Mask[From:] = PreStr
        if MinesAdd:
            return Decimal("-0." + "".join(Mask))

        return Decimal("0." + "".join(Mask))


class TransRepr(object):
    def __init__(self, trans, From, Amnt, Currency, To, Comis):
        self.trans_object = trans
        self.account = From
        self.amnt = Amnt
        self.currency = Currency
        self.order = To
        self.comis = Comis
        
    def __getitem__(self, i):
        if i == 0:
            return self.trans_object
        if i == 1:
            return self.account
        if i == 2:
            return self.amnt
        if i == 3:
            return self.currency
        if i == 4:
            return self.order
        if i == 5:
            return self.comis
        
    def __repr__(self):    
        return "%s %s %s %s" % (From, Amnt, Currency, To, Comis)    
        
        
####make a queue demon here there
### repeat functionality of add_trans
def add_trans2(From, Amnt, Currency, To, status="created", Strict=True, Comis = 0):
    if not isinstance(From, main.account.Account):
        raise TransError("requirment accounts from")

    if not isinstance(To, OrdersMem):
        raise TransError("requirment accounts To")
    Amnt = Decimal(Amnt)
    trans = TransMem(balance1=From.get_balance,
                     user1=From.acc(),
                     order_id=To.id,
                     currency_id=Currency,
                     amnt=Amnt,
                     res_balance1 = Decimal("0.0"),
                     status="core_error")
    trans.save()

    if From.currency <> Currency:
        trans.status = "currency_core"
        trans.save()
        raise TransError("currency_core %s and %s " % (From.currency, Currency))

    if To.currency <> Currency:
        trans.status = "currency_core"
        trans.save()
        raise TransError("currency_core %s and %s " % (To.currency, Currency))

    trans.save()
    NewBalance = 0
        
    if status == "deal" and Comis!=0:
        NewAmnt = Amnt - Amnt*Decimal(Comis)
        NewBalance = From.balance - NewAmnt
        trans.comission = Amnt - NewAmnt
    else:
        NewBalance = From.balance - Amnt
        
        
    if Strict:
        if NewBalance < 0:
            trans.status = "incifition_funds"
            trans.save()
            raise TransError("incifition_funds from %s" % NewBalance)

    ToNewBalance = Decimal(To.sum1) + Decimal(Amnt)
    
    if Strict:
        if ToNewBalance < 0:
            trans.status = "incifition_funds"
            trans.save()
            raise TransError("incifition_funds to %s" % NewBalance)

    #try:
    trans.res_balance1 = NewBalance
    with transaction.atomic():
        To.update(trans, ToNewBalance)
        # race condition
        From.save(trans)
        trans.status=status
    
    trans.save()
     
    #except:
    #    From.reload()
    #    trans.save()
    #    raise TransError("core_error")
    return TransRepr(trans, From, Amnt, Currency, To, Comis)
    

####make a queue demon here there 
def add_trans(From, Amnt, Currency, To, order, status = "created", Out_order_id = None, Strict = True):
       TransPrecession  = settings.TRANS_PREC
       From = Accounts.objects.get(id = From.id)
       To = Accounts.objects.get(id = To.id)

       if Strict and order is  None:
               raise TransError("requirment_params_order")

       if Out_order_id is None and order is not None :
               Out_order_id = str(order.id)

       trans =  Trans(
                      out_order_id = Out_order_id,
                      balance1 = From.balance,
                      balance2 = To.balance,
                      user1 = From,
                      user2 = To,
                      order = order,
                      currency = Currency,
                      amnt = Amnt,
                      status = status
                      )
       trans.save()
       if From.currency <> Currency:
               trans.status = "currency_core"
               trans.save()
               raise TransError("currency_core")

       if To.currency <> Currency:
               trans.status = "currency_core"
               trans.save()
               raise TransError("currency_core")

       FromBalance = From.balance
      

       NewBalance = mines_prec(FromBalance, Amnt, TransPrecession)

       if Strict:
           
           if NewBalance < 0:
                    print "balance and amnt"
                    print FromBalance
                    print Amnt
                    print NewBalance
                    trans.status = "incifition_funds"
                    trans.save()
                    raise TransError("incifition_funds %s-%s = %s" % (FromBalance, Amnt, NewBalance))

       ToBalance = To.balance
       ToNewBalance = plus_prec(ToBalance, Amnt, TransPrecession)
       try :
            From.balance = NewBalance
            From.save()
            To.balance = ToNewBalance
            To.save()
            trans.res_balance1 = NewBalance
            trans.res_balance2 = ToNewBalance
            trans.save()



       except  :
            trans.status = "core_error"
            From.balance = FromBalance
            To.balance  = ToBalance
            From.save()
            To.save()
            trans.save()
            raise TransError("core_error")

## add exception here
       X = True
       if not X :
               raise TransError("cant finish trans")

       
       

#DEPRECATED 
# DO NOT USE for highload operations
####make a queue demon here there only for back capability 
def add_trans111(From, Amnt, Currency, To, order, status="created", Out_order_id=None, Strict=True):
    TransPrecession = settings.TRANS_PREC
    
    From = Accounts.objects.get(id=From.id)
    To = Accounts.objects.get(id=To.id)
    
    if Strict and order is None:
        raise TransError("requirment_params_order")

    if Out_order_id is None and order is not None:
        Out_order_id = str(order.id)

    trans = Trans(out_order_id=Out_order_id,
                  balance1=From.balance,
                  balance2=To.balance,
                  user1=From,
                  user2=To,
                  order=order,
                  currency=Currency,
                  amnt=Amnt,
                  status=status)
    trans.save()

    if From.currency <> Currency:
        trans.status = "currency_core"
        trans.save()
        raise TransError("currency_core")

    if To.currency <> Currency:
        trans.status = "currency_core"
        trans.save()
        raise TransError("currency_core")

    FromBalance = From.balance
    ToBalance = To.balance
    NewBalance = mines_prec(FromBalance, Amnt, TransPrecession)
    ToNewBalance = plus_prec(ToBalance, Amnt, TransPrecession)
    if Strict:
        if NewBalance < 0:
            trans.status = "incifition_funds"
            trans.save()
            raise TransError("incifition_funds")

    mem_order = order.mem_order()
    mem_order.sum1 = Decimal("0.0")
    FromAccount = get_account(user_id=From.user_id, currency_id=Currency.id)
    ToAccount = get_account(user_id=To.user_id, currency_id=Currency.id)
    try:
      Amnt = Decimal(Amnt)
      with transaction.atomic():
         add_trans2(FromAccount, Amnt, Currency.id, mem_order, status, Strict)
         add_trans2(ToAccount, -1*Amnt, Currency.id, mem_order, status, Strict)    
      trans.res_balance1 = NewBalance
      trans.res_balance2 = ToNewBalance
      trans.save()
      return trans
    except:
        mem_order.status = "core_error"
        mem_order.save()
        order.status ='core_error'
        order.save()
        trans.status = "core_error"
	trans.save()
        raise TransError("core_error")
    
   

  

class StockStatAdmin(admin.ModelAdmin):
    list_display = ['VolumeBase', 'VolumeTrade', 'Min', 'Max', 'Start', 'End', 'Stock', "date", "start_date",
                    "end_date", "Status"]
    actions = ["add"]

    def __init__(self, *args, **kwargs):
        super(StockStatAdmin, self).__init__(*args, **kwargs)
        #self.list_display_links = (None, )


class CustomMetaHack(models.Model):
    class Meta:
        verbose_name = u'Метоинформация'
        verbose_name_plural = u'Мета описание для Url'


class CustomMeta(models.Model):
    stack = models.ForeignKey('CustomMetaHack')
    url = models.CharField(max_length=255, verbose_name=u"Относительный url")
    meta_keyword = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, verbose_name=u"Загаловок")

    class Meta:
        verbose_name = u'Метоинформация'
        verbose_name_plural = u'Мета описание для Url'

    def __unicode__(o):
        return o.url


class CustomMetaAdminInline(admin.TabularInline):
    model = CustomMeta
    extra = 50


class CustomMetaHackAdmin(admin.ModelAdmin):
    inlines = [CustomMetaAdminInline]


class StockStat(models.Model):
    VolumeBase = models.DecimalField(max_digits=18,
                                     decimal_places=6,
                                     verbose_name=u"Объем базовой",
                                     default=0)
    VolumeTrade = models.DecimalField(max_digits=18,
                                      decimal_places=6,
                                      verbose_name=u"Объем торга",
                                      default=0)
    Min = models.DecimalField(max_digits=18,
                              decimal_places=6,
                              verbose_name=u"Min",
                              default=0)
    Max = models.DecimalField(max_digits=18,
                              decimal_places=6,
                              verbose_name=u"Max",
                              default=0)
    Start = models.DecimalField(max_digits=18,
                                decimal_places=6,
                                verbose_name=u"Start",
                                default=0)
    End = models.DecimalField(max_digits=18,
                              decimal_places=6,
                              verbose_name=u"End",
                              default=0)
    Stock = models.ForeignKey("TradePairs", verbose_name="Stock")
    STATUS_STAT = (
        ("current", u"Текущий"),
        ("past", u"Прошедший"),
    )
    Status = models.CharField(max_length=40,
                              choices=STATUS_STAT,
                              default='current',
                              editable=False)

    date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата изменение")
    start_date = models.DateTimeField(verbose_name=u"Дата старта")
    end_date = models.DateTimeField(verbose_name=u"Дата конца")

    class Meta:
        verbose_name = u'Японские свечи'
        verbose_name_plural = u'Японские свечи'


class OnlineUsersAdmin(admin.ModelAdmin):
    list_display = ['user', 'pub_date']

    actions = ['hold24', 'hold48', 'hold36', 'hold_week', "ban_chat_1h", "ban_chat_15m", "ban_chat_day", "ban_chat_3h",
               "del_ban", "pin_reset"]

    def caching(self):
        return get_cache('default')

    # pin reset 
    def pin_reset(self, request, queryset):
        for i in queryset:
            obj = PinsImages.objects.get(user=i)
            new_pin4user(obj, request.user)

    def ban_chat_1h(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.user.username, 3600)

    def ban_chat_15m(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.user.username, 900)

    def ban_chat_day(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.user.username, 86000)

    def del_ban(self, req, q):
        cache = self.caching()
        for i in queryset:
            cache.delete("banned_" + i.user.username)

    def ban_chat_3h(self, request, queryset):
        cache = self.caching()
        for i in queryset:
            cache.set("banned_" + i.user.username, 10800)

    def hold24(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i.user, hours=24)
            hold.save()

    def hold48(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i.user, hours=48)
            hold.save()

    def hold36(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i.user, hours=36)
            hold.save()

    def hold_week(self, request, queryset):
        for i in queryset:
            hold = HoldsWithdraw(user=i.user, hours=140)
            hold.save()

            #do something ...

    hold24.short_description = u"Остановить вывод на 24 часа"
    hold_week.short_description = u"Остановить вывод на неделю"
    hold48.short_description = u"Остановить вывод на 48 часа"
    hold36.short_description = u"Остановить вывод на 36 часа"


class OnlineUsers(models.Model):
    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_online",
                             editable=False, unique=True)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата последней активности", editable=False)

    def __unicode__(o):
        return o.user.username + " " + str(o.pub_date)


class OutRequest(models.Model):
    raw_text = models.TextField(verbose_name=u"RAW ")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата", editable=False)
    from_ip = models.CharField(max_length=255,
                               verbose_name=u"IP",
                               blank=True,
                               null=True)
    http_referer = models.CharField(max_length=255,
                                    verbose_name=u"IP",
                                    blank=True,
                                    null=True)


    class Meta:
        verbose_name = u'CallBack запросы'
        verbose_name_plural = u'CallBack запросы'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.from_ip) + " " + str(o.pub_date)


def cancel_p24_in(OrderId):
    order = Orders.objects.get(id=int(OrderId))
    order.status = "canceled"
    order.save()
    return True


def process_p24_in2(OrderId, Description, Comis, DebCred):
    order = Orders.objects.get(id=int(OrderId), status='processing')
    order.status = "processing2"
    order.save()
    add_trans(order.transit_1, order.sum1, order.currency1,
              order.transit_2, order,
              "payin", None, False)
    Comission = order.sum1 * Comis
    add_trans(order.transit_2, Comission, order.currency1,
              order.transit_1, order,
              "comission", None, False)

    order.status = "processed"
    order.save()
    notify_email(order.user, "deposit_notify", DebCred)
    return True


def process_p24_in(OrderId, Description, Comis, Ref, Key=settings.COMMON_SALT):
    order = Orders.objects.get(id=int(OrderId), status="processing")

    DebCred = P24TransIn(ref=Ref,
			 description=Description,
                         currency=order.currency1,
                         amnt=order.sum1,
                         user=order.user,
                         comission=Comis,
                         user_accomplished_id=1,
                         status="created",
                         debit_credit="in",
                         order=order
    )
    DebCred.sign_record(str(Key))
    DebCred.save()
    return DebCred


def cancel_operation(modeladmin, request, queryset):
    for i in queryset:
        if i.user_accomplished is None and (i.status == "processing" or i.status == 'created' ):
            i.status = "canceled"

            order = i.order
            if order is None:
                continue

            order.status = "canceled"
            add_trans(order.transit_2,
                      order.sum1,
                      order.currency2,
                      order.transit_1,
                      order,
                      "canceled",
                      None,
                      False)

            order.save()
            i.user_accomplished = request.user
            i.save()


cancel_operation.short_description = u"Cancel вывод "


class TransOutAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'provider', 'amnt', 'currency', 'user', 'pub_date', 'status']
    list_filter = ['user']
    search_fields = ['ref', 'user', 'wallet']
    actions = [cancel_operation]


class TransOut(models.Model):
    ref = models.CharField(max_length=255,
                           verbose_name=u"Reference",
                           blank=True,
                           null=True)
    wallet = models.CharField(max_length=255,
                              verbose_name=u"wallet",
                              blank=True,
                              null=True)

    provider = models.CharField(max_length=255,
                                verbose_name=u"Provider",
                                blank=True,
                                null=True)

    currency = models.ForeignKey("Currency",
                                 verbose_name=u"Валюта",
                                 editable=False,
                                 blank=True,
                                 null=True)

    amnt = models.DecimalField(max_digits=18,
                               decimal_places=2,
                               verbose_name=u"Сумма",
                               editable=False,
                               blank=True,
                               null=True)

    comission = models.DecimalField(max_digits=18,
                                    decimal_places=2,
                                    verbose_name=u"комиссия",
                                    editable=False,
                                    blank=True,
                                    null=True)

    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_requested_all_out",
                             editable=False,
                             blank=True,
                             null=True)

    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_processed_all_out",
                                          blank=True, null=True, editable=False)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата", editable=False)

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', editable=False, blank=True, null=True, )

    order = models.ForeignKey("Orders", verbose_name=u"Ордер",
                              editable=False, null=True, blank=True)

    sign = models.CharField(max_length=255, blank=True, null=True,
                            editable=False)

    confirm_key = models.CharField(max_length=255, blank=True, null=True,
                                   editable=False)


    def fields4sign(self):
        List = []
        for i in ('amnt', 'wallet', 'user_id', 'provider'):
            Val = getattr(self, i)
            if i in ('amnt', 'comission'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)


    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()


    class Meta:
        verbose_name = u'Вывод'
        verbose_name_plural = u'Выводы'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.amnt) + " " + o.user.username


class TransInAdmin(admin.ModelAdmin):
    list_display = ['ref', 'provider', 'amnt', 'currency', 'user', 'pub_date', 'status']
    list_filter = ['user']
    search_fields = ['ref', 'user']
    actions = []


class TransIn(models.Model):
    ref = models.CharField(max_length=255,
                           verbose_name=u"Reference",
                           blank=True,
                           null=True)

    provider = models.CharField(max_length=255,
                                verbose_name=u"Provider",
                                blank=True,
                                null=True)

    currency = models.ForeignKey("Currency",
                                 verbose_name=u"Валюта",
                                 editable=False,
                                 blank=True,
                                 null=True)
    amnt = models.DecimalField(max_digits=18,
                               decimal_places=2,
                               verbose_name=u"Сумма",
                               editable=False,
                               blank=True,
                               null=True)

    comission = models.DecimalField(max_digits=18,
                                    decimal_places=2,
                                    verbose_name=u"комиссия",
                                    editable=False,
                                    blank=True,
                                    null=True)

    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_requested_all",
                             editable=False,
                             blank=True,
                             null=True)

    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_processed_all",
                                          blank=True, null=True, editable=False)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата", editable=False)

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', editable=False, blank=True, null=True, )

    order = models.ForeignKey("Orders", verbose_name=u"Ордер",
                              editable=False, null=True, blank=True)

    sign = models.CharField(max_length=255, blank=True, null=True,
                            editable=False)


    def fields4sign(self):
        List = []
        for i in ('amnt', 'comission', 'user_id', 'comission'):
            Val = getattr(self, i)
            if i in ('amnt', 'comission'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)


    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()


    class Meta:
        verbose_name = u'Приход'
        verbose_name_plural = u'Приходы'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.amnt) + " " + o.user.username


class P24TransInAdmin(admin.ModelAdmin):
    list_display = ['ref', 'phone', 'user', 'pub_date', 'amnt']
    list_filter = ['phone', 'user']
    search_fields = ['^phone', 'ref', 'user']
    actions = []


class P24TransIn(models.Model):
    phone = models.CharField(max_length=255,
                             verbose_name=u"Phone",
                             blank=True,
                             null=True)

    ref = models.CharField(max_length=255,
                           verbose_name=u"Reference",
                           blank=True,
                           null=True)

    description = models.CharField(max_length=255,
                                   verbose_name=u"Комментарии",
                                   blank=True,
                                   null=True)
    currency = models.ForeignKey("Currency",
                                 verbose_name=u"Валюта",
                                 editable=False,
                                 blank=True,
                                 null=True)
    amnt = models.DecimalField(max_digits=18,
                               decimal_places=2,
                               verbose_name=u"Сумма",
                               editable=False,
                               blank=True,
                               null=True)

    comission = models.DecimalField(max_digits=18,
                                    decimal_places=2,
                                    verbose_name=u"комиссия",
                                    editable=False,
                                    blank=True,
                                    null=True)

    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_requested_p24",
                             editable=False,
                             blank=True,
                             null=True)

    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_processed_p24",
                                          blank=True, null=True, editable=False)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата", editable=False)

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', editable=False, blank=True, null=True, )

    order = models.ForeignKey("Orders", verbose_name=u"Ордер",
                              editable=False, null=True, blank=True)

    debit_credit = models.CharField(max_length=40,
                                    choices=DEBIT_CREDIT,
                                    default='in',
                                    editable=False, blank=True,
                                    null=True, )
    confirm_key = models.CharField(max_length=255, blank=True, null=True,
                                   editable=False)
    sign = models.CharField(max_length=255, blank=True, null=True,
                            editable=False)


    def fields4sign(self):
        List = []
        for i in ('amnt', 'comission', 'user_id', 'description'):
            Val = getattr(self, i)
            if i in ('amnt', 'comission'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)


    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()


    class Meta:
        verbose_name = u'P24 ордер'
        verbose_name_plural = u'P24 ордеры'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.amnt) + " " + o.user.username


class LiqPayTrans(models.Model):
    phone = models.CharField(max_length=255,
                             verbose_name=u"Телефон",
                             editable=True,
                             blank=False,
                             null=False)

    #pib = models.CharField( max_length = 255,
    #verbose_name = u"ФИО",
    #editable = False,
    #blank = False,
    #null = False )

    description = models.CharField(max_length=255,
                                   verbose_name=u"Комментарии",
                                   blank=True,
                                   null=True)
    currency = models.ForeignKey("Currency",
                                 verbose_name=u"Валюта",
                                 editable=True)
    amnt = models.DecimalField(max_digits=18,
                               decimal_places=2,
                               verbose_name=u"Сумма",
                               editable=True)

    comission = models.DecimalField(max_digits=18,
                                    decimal_places=2,
                                    verbose_name=u"комиссия",
                                    editable=False)

    user = models.ForeignKey(User, verbose_name=u"Клиент",
                             related_name="user_requested_liqpay",
                             editable=True, null=True)
    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_processed_liqpay",
                                          blank=True, null=True, editable=False)
    pub_date = models.DateTimeField(auto_now=False, verbose_name=u"Дата", editable=False)

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', editable=True)

    order = models.ForeignKey("Orders", verbose_name=u"Ордер",
                              editable=False, null=True, blank=True)

    debit_credit = models.CharField(max_length=40,
                                    choices=DEBIT_CREDIT,
                                    default='in',
                                    editable=False)
    confirm_key = models.CharField(max_length=255, blank=True, null=True,
                                   editable=False)

    sign = models.CharField(max_length=255, blank=True, null=True,
                            editable=False)


    def fields4sign(self):
        List = []
        for i in ('phone', 'debit_credit', 'status', 'user_id', 'comission', 'amnt', 'description'):
            Val = getattr(self, i)
            if i in ('comission', 'amnt'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)


    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()


    class Meta:
        verbose_name = u'LiqPay ордер'
        verbose_name_plural = u'LiqPay ордеры'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.amnt) + " " + o.user.username


def process_liqpay(modeladmin, request, queryset):
    for i in queryset:
        if i.user_accomplished is None and i.status == "processing" and i.debit_credit == "out":
            i.status = "processed"
            i.order.status = "processed"
            i.order.save()
            i.user_accomplished = request.user
            i.save()


process_liqpay.short_description = u"Process"


###TODO remove various fields from move
class LiqPayTransAdmin(admin.ModelAdmin):
    list_display = ["id", 'phone', 'description', "debit_credit", 'amnt',
                    'currency', "pub_date", "status", "user", "user_accomplished"]
    actions = [process_liqpay]
    list_filter = ('phone', 'user', 'debit_credit', 'user_accomplished')

    search_fields = ['^phone', '^description', '=amnt', '=status']

    def __init__(self, *args, **kwargs):
        super(LiqPayTransAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None, )


    def save_model(self, request, obj, form, change):
        return True


class NewsPageAdmin(admin.ModelAdmin):
    list_display = ["id", 'cat', 'eng_title', 'title', "pub_date"]

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'text':
            return db_field.formfield(widget=TinyMCE(
                attrs={'cols': 200, 'rows': 30},
                #mce_attrs={'external_link_list_url': reverse('tinymce.views.flatpages_link_list')},
            ))
        return super(NewsPageAdmin, self).formfield_for_dbfield(db_field, **kwargs)


class NewsPage(models.Model):
    eng_title = models.CharField(max_length=255, verbose_name=u"Ключ на английском")
    pub_date = models.DateTimeField(default=datetime.now)
    title = models.CharField(max_length=255, verbose_name=u"Заглавие")
    text = models.TextField(verbose_name=u"Текст")
    meta_keyword = models.CharField(max_length=255, blank=True, verbose_name=u"META описание")
    meta_description = models.CharField(max_length=255, blank=True, verbose_name=u"META ключевые слова")
    cat = models.ForeignKey("Category", verbose_name=u"Категория")

    class Meta:
        verbose_name = u'Новость'
        verbose_name_plural = u'Новости'

    def __unicode__(o):
        return o.title


class StaticPageAdmin(admin.ModelAdmin):
    list_display = ["id", 'eng_title', 'title']

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'text':
            return db_field.formfield(widget=TinyMCE(
                attrs={'cols': 200, 'rows': 30},
                #mce_attrs={'external_link_list_url': reverse('tinymce.views.flatpages_link_list')},
            ))
        return super(StaticPageAdmin, self).formfield_for_dbfield(db_field, **kwargs)


class StaticPage(models.Model):
    eng_title = models.CharField(max_length=255, verbose_name=u"Ключ на английском")
    title = models.CharField(max_length=255, verbose_name=u"Заглавие")
    text = models.TextField(verbose_name=u"Текст")
    meta_keyword = models.CharField(max_length=255, blank=True, verbose_name=u"META описание")
    meta_description = models.CharField(max_length=255, blank=True, verbose_name=u"META ключевые слова")

    class Meta:
        verbose_name = u'Статическая страница'
        verbose_name_plural = u'Статические страницы'

    def __unicode__(o):
        return o.title


class Msg(models.Model):
    pub_date = models.DateTimeField(default=datetime.now)
    user_from = models.ForeignKey(User, related_name="user_from_id")
    user_to = models.ForeignKey(User, related_name="user_to_id")
    user_seen_from = models.CharField(max_length=10,
                                      choices=BOOL,
                                      default='false')
    user_seen_to = models.CharField(max_length=10,
                                    choices=BOOL,
                                    default='false')
    user_hide_from = models.CharField(max_length=10,
                                      choices=BOOL,
                                      default='false')
    user_hide_to = models.CharField(max_length=10,
                                    choices=BOOL,
                                    default='false')
    text = models.CharField(max_length=255)

    class Meta:
        verbose_name = u'Внутренняя рассылка'
        verbose_name_plural = u'Внутренняя рассылки'
        ordering = ('-id',)

    def __unicode__(o):
        return o.text


class MsgAdmin(admin.ModelAdmin):
    list_display = ['pub_date', 'user_from', 'user_to', 'user_hide_from', 'user_hide_to', 'text']
    actions = ["add"]
    search_fields = ['^text', '^user_from__username', '^user_to__username']


def process_bank(modeladmin, request, queryset):
    for i in queryset:
        if i.user_accomplished is None and i.status == "processing" and i.debit_credit == "out":
            i.status = "processed"
            i.order.status = "processed"
            i.order.save()
            i.user_accomplished = request.user
            i.save()


process_bank.shoort_description = u"Process"

#TODO banks account
class BankTransfersAdmin(admin.ModelAdmin):
    list_display = ["id", 'ref', 'okpo', 'mfo', 'account', 'description', "debit_credit", 'amnt', 'currency', 'user',
                    'status', "user_accomplished"]
    actions = [process_bank]
    search_fields = ['^okpo', '^mfo', '^account', '^description', '=amnt', '^user__username', '^status']
    exclude = ( "user_accomplished", "status")
    fields = ('ref', 'okpo', 'mfo', 'account', 'description', 'amnt', 'currency')

    def __init__(self, *args, **kwargs):
        super(BankTransfersAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None, )


    def save_model(self, request, obj, form, change):
        ## try to find Account and user by reference
        ###we forbid any regulation after accomplishing transaction onnly manually 

        ###for in bank transfers
        Account = None

        if obj.ref is None or obj.ref == "":
            return False

        obj.debit_credit = "in"
        Account = Accounts.objects.get(reference=obj.ref)
        obj.user = Account.user
        if obj.user is None:
            return False

            ## if we have found  Account and user by reference            
            ## if not by reference, but by users
        TradePair = TradePairs.objects.get(url_title="bank_transfers")
        ##create order for them
        obj.ref = Account.reference
        order = Orders(user=obj.user,
                       currency1=obj.currency,
                       currency2=obj.currency,
                       sum1_history=obj.amnt,
                       sum2_history=obj.amnt,
                       price=obj.amnt,
                       sum1=obj.amnt,
                       sum2=obj.amnt,
                       transit_1=TradePair.transit_on,
                       transit_2=Account,
                       trade_pair=TradePair,
                       status="created"
        )

        order.save()
        add_trans(TradePair.transit_on, obj.amnt, obj.currency, Account, order, "payin", obj.ref, False)
        obj.user_accomplished = request.user
        obj.confirm_key = obj.ref
        obj.order = order
        order.status = "processed"
        order.save()
        obj.status = "processed"
        obj.save()
        ##bank transfer must ref specified for out transfers        
        return True


OBJECTIONS_STAT = (
    ("0", u"0"),
    ("1", u"0.5%"),
    ("2", u"1%"),
    ("manually1", u"1% + 10 грн"),
    ("manually2", u"1% + 1.95 USD")
)


def get_comisP2P(BCard, Amnt):
    try:
        Objections = ObjectionsP2P.objects.get(CardNumber=BCard)
        if Objections.Objection == "0":
            return Amnt
        if Objections.Objection == "1":
            Amnt2 = Amnt / Decimal("1.005")
            return to_prec(Amnt2, 2)
        if Objections.Objection == "2":
            Amnt2 = Amnt / Decimal("1.01")
            return to_prec(Amnt2, 2)
        return -1
    except:
        return -1


class ObjectionsP2P(models.Model):
    CardNumber = models.CharField(max_length=255, verbose_name=u"Номер карты")
    Objection = models.CharField(max_length=255, verbose_name=u"Условия вывода",
                                 choices=OBJECTIONS_STAT, )

    class Meta:
        verbose_name = u'Условие вывода на карту'
        verbose_name_plural = u'Условия выводы на карту'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.CardNumber) + " " + str(o.Objection)


def fix2cancel(modeladmin, request, queryset):
    for i in queryset:
        i.status = "canceled"
        i.user_accomplished = request.user
        i.save()


def fix2auto(modeladmin, request, queryset):
    for i in queryset:
        if i.status == "processing":
            i.status = "auto"
            i.save()


def return_p2p(modeladmin, request, queryset):
    for i in queryset:
        if i.user_accomplished is None and (
                                i.status == "processing" or i.status == 'created' or i.status == "auto" or i.status == "") and i.debit_credit == "out":
            i.status = "canceled"
            order = i.order
            #if order is None:
            #continue 

            order.status = "canceled"
            add_trans(order.transit_2,
                      order.sum1,
                      order.currency2,
                      order.transit_1,
                      order,
                      "canceled",
                      None,
                      False)

            order.save()
            i.user_accomplished = request.user
            i.save()


def P24():
    from sdk.p24 import p24

    return p24()


def p2p_inner_process(user, i):
    i.status = "processed"
    i.order.status = "processed"
    i.order.save()
    i.user_accomplished = user
    i.save()
    notify_email(i.user, "withdraw_notify", i)


def process_p2p(modeladmin, request, queryset):
    for i in queryset:
        if i.user_accomplished is None and (i.status == "core_error"
                                            or i.status == "processing"
                                            or i.status == "auto") and i.debit_credit == "out":
            P = P24()
            CardNumber = i.CardNumber
            CardNumber.replace(" ", "")
            ###this record was processed manually 

            if i.status == "auto":
                try:
                    NewAmnt = get_comisP2P(CardNumber, i.amnt)
                    Result = P.pay2p(i.id, CardNumber, NewAmnt)
                except TransError as e:
                    i.status = "processing"
                    i.save()
                    notify_admin_withdraw_fail(i, e.value)
                    continue
                except Exception as e:
                    i.status = "processing"
                    i.save()
                    notify_admin_withdraw_fail(i, str(e))
                    continue
                if Result:
                    p2p_inner_process(request.user, i)

                continue
            ###this record was processed manually 
            if i.status == "processing" or i.status == "core_error":
                p2p_inner_process(request.user, i)


def p2p_2_vlad_process(modeladmin, request, queryset):
    for i in queryset:
        if i.status == "processing" and i.debit_credit == "out":
            P = P24()
            P.pay2p(i.id, "5211537323989553", i.amnt)
            i.status = 'processing2'
            i.save()


p2p_2_vlad_process.short_description = u"Process to operator"
return_p2p.short_description = u"Cancel"
process_p2p.short_description = u"Process"
fix2auto.short_description = u"Make Auto"
###TODO remove various fields from move



class CardP2PTransfersAdmin(admin.ModelAdmin):
    list_display = ["id", 'CardName', 'CardNumber', "debit_credit", 'amnt',
                    'currency', "pub_date", "status", "user", "user_accomplished"]
    actions = [process_p2p, return_p2p, fix2cancel, fix2auto, p2p_2_vlad_process]
    list_filter = ('CardNumber', 'user', 'debit_credit', 'user_accomplished')
    search_fields = ['CardName', 'CardNumber', '=amnt', 'user__email', 'user__username']

    def __init__(self, *args, **kwargs):
        super(CardP2PTransfersAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None, )


    def save_model(self, request, obj, form, change):
        return True


class BankTransfers(models.Model):
    ref = models.CharField(max_length=255, verbose_name=u"Референс", null=True, blank=True, )
    okpo = models.CharField(max_length=255, verbose_name=u"ОКПО")
    mfo = models.CharField(max_length=255, verbose_name=u"МФО")
    account = models.CharField(max_length=255, verbose_name=u"Счет")
    comission = models.DecimalField(max_digits=18,
                                    decimal_places=2,
                                    verbose_name=u"комиссия",
                                    editable=False)
    description = models.CharField(max_length=255, verbose_name=u"Описание")
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    amnt = models.DecimalField(max_digits=18, decimal_places=2, verbose_name=u"Сумма")
    user = models.ForeignKey(User, verbose_name=u"Клиент", related_name="user_requested", blank=True, null=True)
    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_processed",
                                          blank=True, null=True)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата")
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')
    order = models.ForeignKey("Orders", verbose_name=u"Ордер",
                              editable=False,
                              null=True, blank=True)
    confirm_key = models.CharField(max_length=255, editable=False, blank=True, null=True)

    debit_credit = models.CharField(max_length=40,
                                    choices=DEBIT_CREDIT,
                                    default='in')

    class Meta:
        verbose_name = u'Банковский перевод'
        verbose_name_plural = u'Банковские переводы'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.amnt) + " " + o.currency.title


class ChatHistory(models.Model):
    msg = models.CharField(max_length=255, verbose_name=u"сообщение")
    user = models.CharField(max_length=255, verbose_name=u"пользователь")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")
    CHAT_STATUS = (
        ("created", u"created"),
        ("banned", u"banned"),
    )
    status = models.CharField(max_length=40,
                              choices=CHAT_STATUS,
                              default='created')

    class Meta:
        verbose_name = u'Архив чата'
        verbose_name_plural = u'Архив чата'
        ordering = ('id',)

    def __unicode__(o):
        return o.user + ", " + o.msg


class VolatileConsts(models.Model):
    Name = models.CharField(max_length=255, verbose_name=u"название переменной")
    Value = models.CharField(max_length=255, verbose_name=u"Значение")

    class Meta:
        verbose_name = u'Временная переменная'
        verbose_name_plural = u'Временные переменные'

    ordering = ('id',)

    def __unicode__(o):
        return o.Name + "=" + o.Value


class Chat(models.Model):
    msg = models.CharField(max_length=255, verbose_name=u"сообщение")
    user = models.ForeignKey(User, verbose_name=u"пользователь")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")

    CHAT_STATUS = (
        ("created", u"created"),
        ("banned", u"banned"),
    )
    status = models.CharField(max_length=40,
                              choices=CHAT_STATUS,
                              default='created')

    class Meta:
        verbose_name = u'Сообщение чата'
        verbose_name_plural = u'Сообщения чата'
        ordering = ('id',)

    def __unicode__(o):
        return user + ", " + o.msg


class FullBinInfo(models.Model):
    country = models.CharField(max_length=255, blank=True, null=True)
    product = models.CharField(max_length=255, blank=True, null=True)
    bank = models.CharField(max_length=255, blank=True, null=True)
    bin6 = models.CharField(max_length=255, unique=True)
    prepaid = models.CharField(max_length=255, blank=True, null=True)
    pbbin = models.CharField(max_length=255, blank=True, null=True)
    alphacode = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = u'Бин'
        verbose_name_plural = u'Бины'
        ordering = ('id',)


class ResetPwdLink(models.Model):
    user = models.ForeignKey(User)
    key = models.CharField(max_length=255)
    pub_date = models.DateTimeField(default=datetime.now)
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')

    class Meta:
        verbose_name = u'Ссылка обновления пароля'
        verbose_name_plural = u'Ссылки обновления пароля'
        ordering = ('id',)

    def __unicode__(o):
        return o.user.username + "  " + str(o.pub_date)


class ActiveLink(models.Model):
    user = models.ForeignKey(User)
    key = models.CharField(max_length=255)
    pub_date = models.DateTimeField(default=datetime.now)
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')

    class Meta:
        verbose_name = u'Ссылка активации'
        verbose_name_plural = u'Ссылки активации'
        ordering = ('id',)

    def __unicode__(o):
        return o.user.username + "  " + str(o.pub_date)


class CurrencyAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        Comis = User.objects.get(id=settings.COMISSION_USER)
        Crypto = User.objects.get(id=settings.CRYPTO_USER)

        obj.save()
        if not change:
            for i in User.objects.all():
                d = Accounts(user=i, currency=obj, balance="0.000")
                d.save()

        try:
            ComisAccount = Accounts.objects.get(user=Comis, currency=obj)
        except Accounts.DoesNotExist:
            ComisAccount = Accounts(user=Comis, currency=obj, balance="0.000")
            ComisAccount.save()

        Crypto_Account = None
        try:
            Crypto_Account = Accounts.objects.get(user=Crypto, currency=obj)
        except Accounts.DoesNotExist:
            Crypto_Account = Accounts(user=Crypto, currency=obj, balance="0.000")
            Crypto_Account.save()

        try:
            Tr = TradePairs.objects.get(currency_from=obj,
                                        currency_on=obj,
                                        transit_on=Crypto_Account,
                                        transit_from=Crypto_Account)
        except TradePairs.DoesNotExist:
            trade_pair = TradePairs(
                currency_from=obj,
                currency_on=obj,
                transit_on=Crypto_Account,
                transit_from=Crypto_Account,
                title="CRYPTO_IN_OUT_%s" % (obj.title),
                url_title="crypto_in_out%s" % (obj.title),
                ordering=0
            )
            trade_pair.save()

        return True


class Balances(models.Model):
    account = models.CharField(verbose_name=u"Адресс", max_length=255)
    wallet = models.CharField(verbose_name=u"wallet", max_length=255)
    balance = models.DecimalField(verbose_name=u"Баланс", max_digits=20, decimal_places=10)
    currency = models.ForeignKey("Currency", verbose_name=u"криптовалюта")

    class Meta:
        verbose_name = u'Кошелек'
        verbose_name_plural = u'Кошельки'
        ordering = ('id',)

    def __unicode__(o):
        return o.account + " " + str(o.balance)


class Category(models.Model):
    title = models.CharField(max_length=255, verbose_name=u"Название")
    ordering = models.IntegerField(verbose_name=u"Сортировка", default=1)

    def __unicode__(o):
        return o.title


class Currency(models.Model):
    title = models.CharField(max_length=255, verbose_name=u"Название")
    long_title = models.CharField(max_length=255, verbose_name=u"Длиное название")
    text = models.TextField(verbose_name=u"Описание")
    img = models.ImageField(upload_to='clogo', verbose_name=u'Логотип')
    ordering = models.IntegerField(verbose_name=u"Сортировка", default=1)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")

    class Meta:
        verbose_name = u'Валюта'
        verbose_name_plural = u'Валюты'
        ordering = ('id',)

    def __unicode__(o):
        return o.title


class ChatBan(models.Model):
    user = models.ForeignKey(User, verbose_name=u"Пользователь")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата")
    seconds = models.IntegerField(verbose_name=u"Секунд")

    class Meta:
        verbose_name = u'Бан чата'
        verbose_name_plural = u'Баны чата'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.user.username) + " " + str(o.pub_date) + " on " + str(o.seconds)


class HoldsWithdraw(models.Model):
    user = models.ForeignKey(User, verbose_name=u"Пользователь")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата")
    hours = models.IntegerField(verbose_name=u"кол-во часов")

    class Meta:
        verbose_name = u'Холды вывода'
        verbose_name_plural = u'Холды вывода'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.user.username) + " " + str(o.pub_date) + " on " + str(o.hours)


class PoolAccounts(models.Model):
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')

    user = models.ForeignKey(User, blank=True, null=True)
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")
    address = models.CharField(max_length=255,
                               unique=True,
                               verbose_name=u" Внешний ключ идентификации или кошелек криптовалюты ")

    ext_info = models.CharField(max_length=255,
                               unique=True,
                               verbose_name=u"Дополнительная информация")
    class Meta:
        verbose_name = u'ПулСчетов'
        verbose_name_plural = u'ПулСчета'
        ordering = ('id',)

    def __unicode__(o):
        return o.user.username + " " + str(o.address) + " " + str(o.currency)


class Accounts(models.Model):
    user = models.ForeignKey(User)
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    balance = models.DecimalField(verbose_name=u"Баланс", default=0, max_digits=20, decimal_places=10)
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")
    reference = models.CharField(max_length=255,
                                 null=True,
                                 unique=True,
                                 blank=True,
                                 verbose_name=u" Внешний ключ идентификации или кошелек криптовалюты ")
    last_trans_id = models.IntegerField(verbose_name = "last_trans")
    class Meta:
        verbose_name = u'Счет'
        verbose_name_plural = u'Счета'
        ordering = ('id',)

    def __unicode__(o):
        return o.user.username + " " + str(o.balance) + " " + str(o.currency)


class AccountsAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'currency', 'balance', 'reference', 'pub_date']
    actions = ["add", "delete", "edit"]
    list_filter = ('user', 'currency')

    #exclude = ['balance']
    search_fields = ['^user__username', 'user__email', ]
    #def get_form(self, request, obj=None, **kwargs):
    #    if obj is None:
    #            return super(AccountsAdmin, self).get_form(request, obj, **kwargs)               

    def __init__(self, *args, **kwargs):
        super(AccountsAdmin, self).__init__(*args, **kwargs)
        # self.list_display_links = (None, )


class TradePairs(models.Model):
    title = models.CharField(max_length=255, verbose_name=u"Название")
    url_title = models.CharField(max_length=255, verbose_name=u"Url идентификатор")
    ordering = models.IntegerField(verbose_name=u"Сортировка", default=1)
    transit_on = models.ForeignKey(Accounts,
                                   related_name="transit_account_on",
                                   verbose_name=u"транзитный счет валюты торга")
    transit_from = models.ForeignKey(Accounts, related_name="transit_account_from",
                                     verbose_name=u"транзитный счет базовой валюты")
    currency_on = models.ForeignKey("Currency", related_name="trade_currency_on",
                                    verbose_name=u"Валюта торга")
    currency_from = models.ForeignKey("Currency", related_name="trade_currency_from",
                                      verbose_name=u"Валюта базовая")
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', verbose_name=u"Статус")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата")
    min_trade_base = models.DecimalField(verbose_name=u"минимальный размер сделки валюты торга/комиссия при выводе",
                                         max_digits=12, decimal_places=10, null=True)

    class Meta:
        verbose_name = u'Валютная пара'
        verbose_name_plural = u'Валютные пары'
        ordering = ('id',)

    def __unicode__(o):
        return o.title


def check_holds(order):
    Account = order.transit_2
    Now = timezone.localtime(timezone.now())
    try:
        trans = Trans.objects.get(user2=Account, status="payin")
    except Trans.DoesNotExist:
        hold = HoldsWithdraw(user=order.user, hours=36)
        hold.save()
    except:
        pass


class TransMemAdmin(admin.ModelAdmin):
    list_display = ['id',  'user1', 'order_id', 'balance1',  'currency', 'amnt',
                    'status', 'res_balance1',  'pub_date']
    list_filter = ('status', 'currency')


    def __init__(self, *args, **kwargs):
        super(TransMemAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None, )


class TransMem(models.Model):

    balance1 = models.DecimalField(max_digits=20, editable=False, decimal_places=10, verbose_name=u"Баланс пользователя")
    res_balance1 = models.DecimalField(max_digits=20, editable=False, decimal_places=10,
                                       verbose_name=u"Баланс пользователя")
    user1 = models.ForeignKey(Accounts, related_name="from_mem",
                              verbose_name="Счет пользователя")
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    amnt = models.DecimalField(max_digits=20, decimal_places=10, verbose_name=u"Сумма")
    comission = models.DecimalField(max_digits=20, default=0, decimal_places=10, verbose_name=u"Сумма")

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', verbose_name=u"Статус")
    order_id = models.IntegerField(verbose_name=u"Ордер")
    pub_date = models.DateTimeField(default=datetime.now, blank=True, verbose_name=u"Дата", editable=False)


    class Meta:
        verbose_name = u'Транзакция в памяти'
        verbose_name_plural = u'Транзакции в памяти'
        ordering = ('-id',)

    def __unicode__(o):
        return o.order_id


class Trans(models.Model):
    out_order_id = models.CharField(max_length=255, verbose_name="Внешний order",
                                    null=True, blank=True)
    balance1 = models.DecimalField(max_digits=20, editable=False,
                                   decimal_places=10, verbose_name=u"Баланс отправителя")
    balance2 = models.DecimalField(max_digits=20, editable=False, 
                                   decimal_places=10, verbose_name=u"Баланс получателя")

    res_balance1 = models.DecimalField(max_digits=20, editable=False, decimal_places=10,
                                       verbose_name=u"Баланс отправителя")
    res_balance2 = models.DecimalField(max_digits=20, editable=False, decimal_places=10,
                                       verbose_name=u"Баланс получателя")
    user1 = models.ForeignKey(Accounts, related_name="from_account",
                              verbose_name="Счет отправителя")
    user2 = models.ForeignKey(Accounts, related_name="to_account",
                              verbose_name="Счет получателя")
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    amnt = models.DecimalField(max_digits=20, decimal_places=10, verbose_name=u"Сумма")
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created', verbose_name=u"Статус")
    order = models.ForeignKey("Orders", verbose_name=u"Ордер", blank=True, null=True)

    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата", editable=False)


    class Meta:
        verbose_name = u'Транзакция'
        verbose_name_plural = u'Транзакции'
        ordering = ('-id',)

    def __unicode__(o):
        return o.out_order_id


def cancel_trans(modeladmin, request, queryset):
    for obj in queryset:
        add_trans(obj.user2,
                  obj.amnt,
                  obj.currency,
                  obj.user1,
                  obj.order,
                  "canceled",
                  obj.id,
                  False)


cancel_trans.short_description = u"Cancel Trans"


class TransAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'user1', 'balance1', 'user2', 'balance2', 'currency', 'amnt', 'status',
                    'res_balance1', 'res_balance2', 'pub_date']
    list_filter = ('status', 'currency')

    actions = ["add", cancel_trans]

    def save_model(self, request, obj, form, change):
        return True


    def __init__(self, *args, **kwargs):
        super(TransAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None, )


# this strips the html, so people will have the text as well.
# create the email, and attach the HTML version as well.

class CryptTest(models.Model):
    msg = models.CharField(max_length=255)

    def crypt(self):
        obj = get_crypto_object()
        self.msg = base64.b32encode(obj.encrypt(self.msg))
        self.save()

    def decrypt(self):
        obj = get_crypto_object()
        self.msg = obj.decrypt(base64.b32decode(self.msg))
        self.save()


## WARNING instance should be decrypted
def check_sign(instance, crypto_obj, salt):
    ClassName = str(instance.__class__)
    Subject = instance.id
    try:
        D = Signs.objects.get(subject=Subject, object_type=ClassName)
        decrypted_sign = common_decrypt(crypto_obj, D.sign)
        if decrypted_sign == generate_key_from2(instance.salt_repr(), salt):
            return True
        else:
            return False
    except:
        return False


class Signs(models.Model):
    subject = models.IntegerField()
    object_type = models.CharField(max_length=255)
    sign = models.CharField(max_length=255)

    class Meta:
        verbose_name = u'Подпись'
        verbose_name_plural = u'Подписи'


def save_sign(sign, instance):
    D = Signs(subject=instance.id, object_type=str(instance.__class__), sign=sign)
    D.sign = sign
    D.save()


## TODO на уровне хуков и базы данных for  weak defender from raw database change
class history_change(models.Model):
    Subject = models.IntegerField()
    Class = models.CharField(max_length=255)
    status = models.CharField(max_length=40, choices=STATUS_ORDER, default='created', verbose_name=u"Статус")

    class Meta:
        verbose_name = u'История изменений'
        verbose_name_plural = u'История изменений'


TYPE = (
    ("sell", u"sell"),
    ("buy", u"buy"),
    ("transfer", u"transfer"),
)

class DealsMemoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'type_deal', 'price', 'amnt_base', 'amnt_trade', 'trade_pair', 'pub_date']
    list_filter = ('user', 'trade_pair','price')


class DealsMemory(models.Model):
    user_id = models.IntegerField()
    type_deal = models.CharField(max_length=40, choices=TYPE, default='buy', verbose_name=u"Тип")
    user = models.CharField(max_length=255, verbose_name=u"Username")
    price = models.DecimalField(max_digits=20,
                                blank=True,
                                decimal_places=10, verbose_name=u"цена")

    amnt_base = models.DecimalField(max_digits=20,
                                    blank=True,
                                    decimal_places=10, verbose_name=u"сумма в базовой валюте")
    amnt_trade = models.DecimalField(max_digits=20,
                                     blank=True,
                                     decimal_places=10, verbose_name=u"сумма в валюты торга")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата ")
    trade_pair = models.IntegerField(verbose_name=u"Валютная пара")

    class Meta:
        verbose_name = u'Сделка'
        verbose_name_plural = u'Сделки'

    def fields4sign(self):
        List = []
        for i in ('type_deal', 'user_id'):
            Val = getattr(self, i)
            if i in ('amnt_base', 'amnt_trade'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)

    def __unicode__(self):
        return self.fields4sign()





class OrdersMemArchiveAdmin(admin.ModelAdmin):
    list_display = ['user', 'trade_pair', 'price', 'currency1', 'sum1_history', 'sum1', 'currency2', 'status', 'pub_date']
    list_filter = ('user', 'currency1', 'currency2', 'status')


class OrdersMemArchive(models.Model):
    user = models.IntegerField()
    trade_pair = models.IntegerField(verbose_name=u"Валютная пара")
    currency1 = models.IntegerField(verbose_name=u"Валюта", )
    sum1_history = models.DecimalField(verbose_name=u"Изначальная сумма продажи", max_digits=20, decimal_places=10)
    price = models.DecimalField(verbose_name=u"Цена", max_digits=24, decimal_places=16, blank=True)
    sum1 = models.DecimalField(verbose_name=u"сумма продажи", max_digits=20, decimal_places=10)
    status = models.CharField(max_length=40, choices=STATUS_ORDER, default='created', verbose_name=u"Статус")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")
    comission = models.DecimalField(max_digits=20, default='0.0005', blank=True, decimal_places=10,
                                    verbose_name=u"Комиссия")
    sign = models.CharField(max_length=255, verbose_name=u"Custom sign")
    last_trans_id = models.IntegerField(verbose_name=u"last id", blank=True, null=True)
    currency2 = models.IntegerField(blank=True, verbose_name=u"Валюта Б", )
    type_deal = models.CharField(max_length=40, choices=TYPE, default='transfer', verbose_name=u"Тип")
        
        
        
class OrdersMemAdmin(admin.ModelAdmin):
    list_display = ['user', 'trade_pair', 'price', 'currency1', 'sum1_history', 'sum1', 'currency2', 'status', 'pub_date']
    list_filter = ('user', 'currency1', 'currency2', 'status')
"""
order1_id   | int(11)        | NO   |     | NULL              |                |
| order2_id   | int(11)        | NO   |     | NULL              |                |
| amnt        | decimal(24,16) | YES  |     | NULL              |                |
| currency_id | int(11)        | NO   |     | NULL              |                |
| for_amnt    | decimal(24,16) | YES  |     | NULL              |                |
| pub_date    | timestamp      | NO   |     | CURRENT_TIMESTAMP |                |
| status      | varchar(40)    | YES  |     | processing        |                |
+-------------+----------------+------+-----+-------------------+-------------
"""

class Deals(models.Model):
        
    order1 = models.ForeignKey('Orders', verbose_name=u"ордер продавец", related_name="order_buyer")
    order2 = models.ForeignKey('Orders', verbose_name=u"ордер покупатель", related_name="order_seller")
    amnt = models.DecimalField(verbose_name=u"Сумма", max_digits=20, decimal_places=10)
    for_amnt = models.DecimalField(verbose_name=u"Сумма ", max_digits=20, decimal_places=10)
    status = models.CharField(max_length=40, choices=STATUS_ORDER, default='processing', verbose_name=u"Статус")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")
    currency_id = models.IntegerField(verbose_name=u"Валюта", )
    trade_pair_id = models.IntegerField(verbose_name=u"Пара", )
    user1_id = models.IntegerField(verbose_name=u"Пользователь1", )
    user2_id = models.IntegerField(verbose_name=u"Пользователь2", )

class OrdersMem(models.Model):
    user = models.IntegerField()
    trade_pair = models.IntegerField(verbose_name=u"Валютная пара")
    currency1 = models.IntegerField(verbose_name=u"Валюта", )
    sum1_history = models.DecimalField(verbose_name=u"Изначальная сумма продажи", max_digits=20, decimal_places=10)
    price = models.DecimalField(verbose_name=u"Цена", max_digits=24, decimal_places=16, blank=True)
    sum1 = models.DecimalField(verbose_name=u"сумма продажи", max_digits=20, decimal_places=10)
    status = models.CharField(max_length=40, choices=STATUS_ORDER, default='created', verbose_name=u"Статус")
    pub_date = models.DateTimeField(default=datetime.now, blank=True, verbose_name=u"Дата публикации")
    comission = models.DecimalField(max_digits=20, default='0.0005', blank=True, decimal_places=10,
                                    verbose_name=u"Комиссия")
    sign = models.CharField(max_length=255, verbose_name=u"Custom sign")
    last_trans_id = models.IntegerField(verbose_name=u"last id", blank=True, null=True)
    currency2 = models.IntegerField(blank=True, verbose_name=u"Валюта Б", )
    type_deal = models.CharField(max_length=40, choices=TYPE, default='transfer', verbose_name=u"Тип")

    
    @property
    def currency(self):
        return self.currency1
        
    def update(self, trans, new_amnt):
        # TODO rewrite to update statemant
        
        count = OrdersMem.objects.filter(last_trans_id=self.last_trans_id, 
                                         id=self.id).update(last_trans_id=trans.id, sum1=new_amnt)
        if count!=1:
            raise TransError("race condition at order %s" % self)
        
        self.last_trans_id = trans.id
        self.sum1 = new_amnt
        

    class Meta:
        verbose_name = u'Заявка'
        verbose_name_plural = u'Заявки'
        ordering = ('-id',)

    def make2processed(self):
        self.status = "processed"
        self.save()

    def archive(self):
        OrdersMemArchive(user=self.user,
                        trade_pair=self.trade_pair,
                        currency1=self.currency1,
                        sum1_history=self.sum1_history,
                        price=self.price,
                        sum1=self.sum1,
                        status=self.status,
                        pub_date=self.pub_date,
                        comission=self.comission,
                        sign=self.sign,
                        last_trans_id=self.last_trans_id,
                        currency2=self.currency2,
                        type_deal=self.type_deal).save()
        
        

    def salt_repr(self):
        return ",".join([str(getattr(self, field.name)) for field in self._meta.local_fields])

    def save_model(self, request, obj, form, change):
        checksum(self)
        super(OrdersMem, self).save(request, obj, form, change)


    def fields4sign(self):
        List = []
        for i in ('currency1', 'sum1_history', 'sum1',
                  'price', 'last_trans_id', 'user', 'comission'):
            Val = getattr(self, i)
            if i in ('sum1_history', 'sum1', 'sum2', 'comission'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)

    def stable_order(self, key):
        ### account buyer, sum to buy, item - order seller, Order - order buyer
        TradePair = TradePairs.objects.get(id = self.trade_pair)
        (sum2, sum2_history) = (None, None)
        if TradePair.currency_on.id == Currency1.id:
              transit1 = TradePair.transit_on
              transit2 = TradePair.transit_from
              sum2 = self.sum1*self.price
              sum2_history = self.sum1_history*self.price
        else :
              transit2 = TradePair.transit_on
              transit1 = TradePair.transit_from  
              sum2 = self.sum1/self.price
              sum2_history = self.sum1_history/self.price
        
        Mem = Orders(user_id=self.user,
                     trade_pair_id=self.trade_pair,
                     currency1_id=self.currency1,
                     sum1_history=self.sum1_history,
                     price=self.price,
                     sum1=self.sum1,
                     pub_date=self.pub_date,
                     currency2_id=self.currency2,
                     sum2_history=sum2_history,
                     sum2=sum2,
                     status=self.status,
                     transit_1_id=transit_1,
                     transit_2_id=transit_2,
                     comission=self.comission)

        Mem.sign_record(key)
        Mem.save()
        return Mem

    def __unicode__(self):
        return self.fields4sign()

    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()


class Orders(models.Model):
    user = models.ForeignKey(User)
    trade_pair = models.ForeignKey(TradePairs, verbose_name=u"Валютная пара")
    currency1 = models.ForeignKey("Currency", related_name='from_currency', verbose_name=u"Валюта A", )
    sum1_history = models.DecimalField(verbose_name=u"Изначальная сумма продажи", max_digits=20, decimal_places=10)
    price = models.DecimalField(verbose_name=u"Цена", max_digits=24, decimal_places=16, blank=True)
    sum1 = models.DecimalField(verbose_name=u"сумма продажи", max_digits=20, decimal_places=10)
    currency2 = models.ForeignKey("Currency", related_name='to_currency', verbose_name=u"Валюта Б", )
    sum2_history = models.DecimalField(verbose_name=u"Изначальная сумма покупки", max_digits=20, decimal_places=10)
    sum2 = models.DecimalField(verbose_name=u"сумма покупки", max_digits=20, decimal_places=10)
    status = models.CharField(max_length=40, choices=STATUS_ORDER, default='created', verbose_name=u"Статус")
    pub_date = models.DateTimeField(default=datetime.now, verbose_name=u"Дата публикации")
    transit_1 = models.ForeignKey(Accounts, related_name="transit_account_1", verbose_name=u"транзитный счет покупки")
    transit_2 = models.ForeignKey(Accounts, related_name="transit_account_2", verbose_name=u"транзитный счет продажи")
    comission = models.DecimalField(max_digits=20, default='0.0005', blank=True, decimal_places=10,
                                    verbose_name=u"Комиссия")
    sign = models.CharField(max_length=255, default='0.0005', verbose_name=u"Custom sign")

    # May be we can setup this
    def salt_repr(self):
        return ",".join([str(getattr(self, field.name)) for field in self._meta.local_fields])

    def fields4sign(self):
        List = []
        for i in ('currency1', 'currency2', 'sum1_history', 'sum2_history', 'sum1', 'sum2',
                  'transit_1', 'transit_2', 'user_id', 'trade_pair'):
            Val = getattr(self, i)
            if i in ('sum1_history', 'sum2_history', 'sum1', 'sum2'):
                List.append(format_numbers_strong(Val))
            else:
                List.append(str(Val))

        return ",".join(List)


    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()

    def save_model(self, *args, **kwargs):
        checksum(self)
        super(Orders, self).save(*args, **kwargs)

    
    #user = models.IntegerField(User)
    #trade_pair = models.IntegerField(verbose_name=u"Валютная пара")
    #currency1 = models.IntegerField(verbose_name=u"Валюта", )
    #sum1_history = models.DecimalField(verbose_name=u"Изначальная сумма продажи", max_digits=20, decimal_places=10)
    #price = models.DecimalField(verbose_name=u"Цена", max_digits=24, decimal_places=16, blank=True)
    #sum1 = models.DecimalField(verbose_name=u"сумма продажи", max_digits=20, decimal_places=10)
    #status = models.CharField(max_length=40, choices=STATUS_ORDER, default='created', verbose_name=u"Статус")
    #pub_date = models.DateTimeField(auto_now=True, verbose_name=u"Дата публикации")
    #comission = models.DecimalField(max_digits=20, default='0.0005', blank=True, decimal_places=10,
                                    #verbose_name=u"Комиссия")
    #sign = models.CharField(max_length=255, verbose_name=u"Custom sign")
    #last_trans_id = models.IntegerField(verbose_name=u"last id", blank=True, null=True)
    #currency2 = models.IntegerField(blank=True, verbose_name=u"Валюта Б", )

        

    def mem_order(self):
        Mem = OrdersMem(
                    user=self.user_id,
                    trade_pair=self.trade_pair.id,
                    currency1=self.currency1.id,
                    sum1_history=self.sum1_history,
                    price=self.price,
                    sum1=self.sum1,
                    currency2=self.currency2.id,
                    status=self.status,
                    comission=self.comission)
        Mem.save()
        return Mem


    class Meta:
        verbose_name = u'Сделка'
        verbose_name_plural = u'Сделки'
        ordering = ('-id',)

    def __unicode__(o):
        return str(o.id)


def process_p24_in_orders(order, Description, Comis):
    add_trans(order.transit_1, order.sum1, order.currency1,
              order.transit_2, order,
              "payin", None, False)
    Comission = order.sum1 * Comis
    add_trans(order.transit_2, Comission, order.currency1,
              order.transit_1, order,
              "comission", None, False)

    DebCred = P24TransIn(
        description=Description,
        currency=order.currency1,
        amnt=order.sum1,
        user=order.user,
        comission=Comission,
        user_accomplished_id=1,
        status="processed",
        debit_credit="in",
        order=order
    )
    DebCred.save()
    order.status = "processed"
    order.save()
    notify_email(order.user, "deposit_notify", DebCred)
    return True


def manually_process(modeladmin, request, queryset):
    for i in queryset:
        process_p24_in_orders(i, "manually from admin", Decimal("0.02"))


manually_process.short_description = "for mistakes"


class OrdersAdmin(admin.ModelAdmin):
    list_display = ['user', 'trade_pair', 'price', 'currency1', 'sum1_history', 'sum1', 'currency2', 'sum2_history',
                    'sum2', 'status', 'pub_date']
    list_filter = ('user', 'currency1', 'currency2', 'status')
    actions = ["manually_process"]


def dictfetchall(cursor, Query):
    "Returns all rows from a cursor as a dict"
    List = cursor.fetchall()
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in List
    ]


#CRYPTO BANK TRANSFERS
def crypton_in(obj, user_accomplished):
    if False and not obj.verify(settings.CRYPTO_SALT):
        return

    TradePair = TradePairs.objects.get(currency_on=obj.currency,
                                       currency_from=obj.currency)

    AccountTo = Accounts.objects.get(user=obj.user,
                                     currency=obj.currency)
    ##create order for them
    order = Orders(user=obj.user,
                   currency1=obj.currency,
                   currency2=obj.currency,
                   sum1_history=obj.amnt,
                   sum2_history=obj.amnt,
                   price=obj.amnt,
                   sum1=obj.amnt,
                   sum2=obj.amnt,
                   transit_1=TradePair.transit_on,
                   transit_2=AccountTo,
                   trade_pair=TradePair,
                   status="processed"
    )
    order.save()
    add_trans(TradePair.transit_on, obj.amnt, obj.currency,
              AccountTo, order, "payin", obj.crypto_txid, False)
    obj.order = order
    order.save()
    obj.status = "processed"
    obj.sign_record(settings.CRYPTO_SALT)
    obj.user_accomplished = user_accomplished
    obj.save()
    notify_email(obj.user, "deposit_notify", obj)


class btce_trade_stat_minute_usdAdmin(admin.ModelAdmin):
    list_display = ['datetime', 'unixtime', 'price', 'amount', 'ask_bid', 'stock_type']
    list_filter = ['stock_type']


class btce_trade_stat_minute_usd(models.Model):
    unixtime = models.IntegerField(verbose_name=u"UnixDate")
    btc_tid = models.IntegerField(verbose_name=u"btc_tid")
    # TODO remove auto_now = True
    datetime = models.DateTimeField(default=datetime.now,
                                    verbose_name=u"Дата")
    price = models.DecimalField(verbose_name=u"Цена", max_digits=20, decimal_places=10)
    amount = models.DecimalField(verbose_name=u"Сумма", max_digits=20, decimal_places=10)
    STATUS_ORDER = (
        ("ask", u"продажа"),
        ("bid", u"покупка"),
    )
    ask_bid = models.CharField(max_length=40,
                               choices=STATUS_ORDER,
                               verbose_name=u"Тип")

    stock_type = models.CharField(max_length=40,
                                  verbose_name=u"Рынок", default="btc_usd")


    class Meta:
        verbose_name = u'BTCe BTC/USD'
        verbose_name_plural = u'BTCe BTC/USD'
        ordering = ('-id',)


def process(modeladmin, request, queryset):
    for obj in queryset:

        if obj.user_accomplished is None and obj.status == "processing":
            obj.status = "processed"
            obj.user_accomplished = request.user
            obj.save()
            if obj.debit_credit == "in":
                crypton_in(obj, request.user)
            else:
                pass


def crypto_cancel(obj):
    TradePair = TradePairs.objects.get(currency_on=obj.currency,
                                       currency_from=obj.currency)
    AccountTo = Accounts.objects.get(user=obj.user,
                                     currency=obj.currency)
    ##create order for them
    add_trans(AccountTo, obj.amnt, obj.currency,
              TradePair.transit_on, obj.order, "canceled",
              obj.crypto_txid, False)
    obj.order.status = "canceled"
    obj.order.save()
    obj.status = "canceled"
    obj.save()


def crypto_cancel_out(obj, reason="by admin command", comis=True):
    TradePair = TradePairs.objects.get(currency_on=obj.currency,
                                       currency_from=obj.currency)
    AccountTo = Accounts.objects.get(user=obj.user,
                                     currency=obj.currency)
    ##create order for them
    amnt_back  = None
    if comis:
      amnt_back = obj.amnt + obj.comission
    else:
      amnt_back = obj.amnt

    add_trans(TradePair.transit_on, amnt_back, obj.currency,
              AccountTo, obj.order, "order_cancel",
              obj.crypto_txid, False)
    obj.order.status = "canceled"
    obj.order.save()
    obj.tx_archive = reason
    obj.status = "canceled"
    obj.save()




def crypto_cancel_action(modeladmin, request, queryset):
    for obj in queryset:
        if obj.status == "processed" and obj.debit_credit == "in":
            crypto_cancel(obj)

        if obj.status == "processing" and obj.debit_credit == "out":
            crypto_cancel_out(obj)


process.short_description = u"Process"
crypto_cancel_action.short_description = u"Cancel"


class CryptoTransfersAdmin(admin.ModelAdmin):
    list_display = ['confirms', 'account', 'description', "debit_credit", 'amnt', "comission", 'currency', 'user',
                    'status', "crypto_txid", "user_accomplished", "pub_date"]
    actions = ["add", process, crypto_cancel_action]
    list_filter = ('currency', 'user', 'user_accomplished', 'status')
    search_fields = ['account', 'description', '=amnt']
    exclude = ( "user_accomplished", "status")
    fields = ('account', 'description', "debit_credit", 'amnt', 'crypto_txid', 'currency')

    def __init__(self, *args, **kwargs):
        super(CryptoTransfersAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None, )

    ### TODO add foreign check of transactions txid        
    def save_model(self, request, obj, form, change):
        ## try to find Account and user by reference
        ###we forbid any regulation after accomplishing transaction onnly manually 
        if obj.user_accomplished is not None:
            return False

        if obj.debit_credit == "out":
            return False

        if obj.crypto_txid is None or len(obj.crypto_txid) < 64:
            return False

        Account = None
        if obj.account is not None and obj.account != "":
            Account = Accounts.objects.get(reference=obj.account)
            obj.user = Account.user

        if obj.user is not None:
            ## if we have found  Account and user by reference
            AccountTo = None

            if Account is not None:
                AccountTo = Account
            else:
                AccountTo = Accounts.objects.get(user=obj.user,
                                                 currency=obj.currency)
            ## if not by reference, but by users
            obj.ref = Account.reference
            obj.currency = Account.currency

            TradePair = TradePairs.objects.get(currency_on=obj.currency, currency_from=obj.currency)

            ##create order for them
            order = Orders(user=obj.user,
                           currency1=obj.currency,
                           currency2=obj.currency,
                           sum1_history=obj.amnt,
                           sum2_history=obj.amnt,
                           price=obj.amnt,
                           sum1=obj.amnt,
                           sum2=obj.amnt,
                           transit_1=TradePair.transit_on,
                           transit_2=AccountTo,
                           trade_pair=TradePair,
                           status="created"
            )
            order.save()
            add_trans(TradePair.transit_on, obj.amnt, obj.currency, AccountTo, order, "payin", obj.ref, False)
            obj.order = order
            order.status = "processed"
            order.save()
            obj.user_accomplished = request.user
            obj.status = "processed"
            obj.save()

            return True

            ##if we have a transaction accomplished - do nothing


class CardP2PTransfers(models.Model):
    CardNumber = models.CharField(max_length=255, verbose_name=u"Номер карты")
    CardName = models.CharField(max_length=255, verbose_name=u"Имя держателя на карте")
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    amnt = models.DecimalField(max_digits=18, decimal_places=2, verbose_name=u"Сумма")
    user = models.ForeignKey(User,
                             verbose_name=u"Клиент",
                             related_name="user_requested_card",
                             blank=True, null=True)
    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_processed_card",
                                          blank=True, null=True)

    comission = models.DecimalField(max_digits=18,
                                    decimal_places=2,
                                    verbose_name=u"комиссия",
                                    editable=False,
                                    blank=True,
                                    null=True)

    pub_date = models.DateTimeField(auto_now=False,
                                    verbose_name=u"Дата")

    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')

    order = models.ForeignKey("Orders",
                              verbose_name=u"Ордер",
                              editable=False,
                              null=True,
                              blank=True)

    sign = models.CharField(max_length=255,
                            editable=False,
                            blank=True,
                            null=True)

    confirm_key = models.CharField(max_length=255,
                                   editable=False,
                                   blank=True,
                                   null=True)

    debit_credit = models.CharField(max_length=40,
                                    choices=DEBIT_CREDIT,
                                    default='out')

    def salt_repr(self):
        return ",".join([str(getattr(self, field.name)) for field in self._meta.local_fields])


    def fields4sign(self):
        List = []
        for i in ('CardNumber', 'currency', 'amnt', 'user_id', 'comission', 'status', 'confirm_key'):
            Val = getattr(self, i)
            List.append(str(Val))

        return ",".join(List)


    def verify(self, key):
        Fields = self.fields4sign()
        Sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        return Sign == self.sign

    def sign_record(self, key):
        Fields = self.fields4sign()
        self.sign = generate_key_from2(Fields, key + settings.SIGN_SALT)
        self.save()


    # WARNING transaction to payments account must be first
    def save_model(self, *args, **kwargs):

        checksum(self)
        super(CardP2PTransfers, self).save(*args, **kwargs)


    class Meta:
        verbose_name = u'Вывод на карту'
        verbose_name_plural = u'Выводы на карту'

    ordering = ('id',)

    def __unicode__(o):
        return str(o.id) + " " + str(o.amnt) + " " + o.currency.title

class CryptoRawTrans(models.Model):
    crypto_txid = models.CharField(max_length=255, blank=True, null=True)
    tx_archive = models.TextField(blank=True, null=True)
    block_height = models.IntegerField( default=0)
    pub_date = models.DateTimeField(default=datetime.now)
 
class CryptoTransfers2(models.Model):
    account = models.CharField(max_length=255, verbose_name=u"Счет")
    description = models.CharField(max_length=255, verbose_name=u"Описание", blank=True)
    payment_id = models.CharField(max_length=255, verbose_name=u"Payment Id", blank=True)
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта", related_name="currency_2")
    amnt = models.DecimalField(max_digits=18, decimal_places=10, verbose_name=u"Сумма")
    user = models.ForeignKey(User, verbose_name=u"Клиент", related_name="user_crypto_requested2")
    comis_tid = models.ForeignKey(Trans, verbose_name=u"Транзакция комиссии", related_name="trans_comis_trans2")
    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_crypto_processed2",
                                          blank=True, null=True)
    confirms = models.IntegerField(verbose_name=u" Подтверждения", default=0)
    pub_date = models.DateTimeField(default=datetime.now,
                                    verbose_name=u"Дата")
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')
    comission = models.DecimalField(max_digits=18,
                                    decimal_places=10,
                                    verbose_name=u"комиссия",
                                    editable=False)
    confirm_key = models.CharField(max_length=255, editable=False, blank=True, null=True)
    crypto_txid = models.CharField(max_length=255, blank=True, null=True)

    debit_credit = models.CharField(max_length=40,
                                    choices=DEBIT_CREDIT,
                                    default='in')

    tx_archive = models.TextField(blank=True, null=True)

    order = models.ForeignKey(
        "Orders", verbose_name=u"Ордер",
        editable=False,
        null=True,
        blank=True)



class CryptoTransfers(models.Model):
    account = models.CharField(max_length=255, verbose_name=u"Счет")
    description = models.CharField(max_length=255, verbose_name=u"Описание", blank=True)
    payment_id = models.CharField(max_length=255, verbose_name=u"Payment Id", blank=True)
    currency = models.ForeignKey("Currency", verbose_name=u"Валюта")
    amnt = models.DecimalField(max_digits=18, decimal_places=10, verbose_name=u"Сумма")
    user = models.ForeignKey(User, verbose_name=u"Клиент", related_name="user_crypto_requested")
    comis_tid = models.ForeignKey(Trans, verbose_name=u"Транзакция комиссии", related_name="trans_comis_trans")
    user_accomplished = models.ForeignKey(User, verbose_name=u"Оператор проводки",
                                          related_name="operator_crypto_processed",
                                          blank=True, null=True)
    confirms = models.IntegerField(verbose_name=u" Подтверждения", default=0)
    pub_date = models.DateTimeField(default=datetime.now,
                                    verbose_name=u"Дата")
    status = models.CharField(max_length=40,
                              choices=STATUS_ORDER,
                              default='created')
    comission = models.DecimalField(max_digits=18,
                                    decimal_places=10,
                                    verbose_name=u"комиссия",
                                    editable=False)
    confirm_key = models.CharField(max_length=255, editable=False, blank=True, null=True)
    crypto_txid = models.CharField(max_length=255, blank=True, null=True)
    tx_archive = models.TextField(blank=True, null=True)

    order = models.ForeignKey(
        "Orders", verbose_name=u"Ордер",
        editable=False,
        null=True,
        blank=True)

    sign = models.CharField(verbose_name=u"подпись клиента", max_length=255, null=False)

    def salt_fields(self):
        return ('account', 'debit_credit', 'currency', 'amnt', 'status',
                'user_id', 'confirm_key', 'confirms', 'crypto_txid')

    def verify(self, key):
        Fields = self.salt_fields()
        StableData = ",".join([str(getattr(self, field)) for field in Fields])
        if generate_key_from2(StableData, key + settings.SIGN_SALT) == self.sign:
            return True
        else:
            return False

    def salt_repr(self):
        return ",".join([str(getattr(self, field.name)) for field in self._meta.local_fields])

    def save_model(self, request, obj, form, change):
        checksum(self)
        super(CryptoTransfers, self).save(request, obj, form, change)


