# -*- coding: utf-8 -*-
from  django.core.exceptions import ValidationError
from django import forms
# from captcha.fields import CaptchaField
from django.contrib.auth.models import User
from main.models import Currency, Accounts, HoldsWithdraw, TradePairs, PinsImages
from decimal import Decimal, getcontext
from datetime import datetime
import math
from django.utils.translation import ugettext as _
from main.http_common import generate_key_from
from main.account import get_account
from django.utils.html import mark_safe
import crypton.settings as settings
import json
import urllib2
from django.utils.timezone import utc

class PinWidget(forms.widgets.Textarea):
    def render(self, name, value, attrs=None):
        # Build a dictionary linking purchase requests
        # with their corresponding assets

        # Start with the textarea; and wrap it in a script
        # containing the logic to populate it, and the
        # button to trigger the script.
        html = """
        <div id='container_""" + name + """'></div>
        <input type="hidden" value="" id='id_""" + name + """' name='""" + name + """'>
        """;
        # Since we are using string concatenation, we need to
        # mark it as safe in order for it to be treated as
        # html code.
        return mark_safe(html)


class PinField(forms.Field):
    widget = PinWidget

    default_error_messages = {
        'not_an_a': _(u"Неверный PIN")
    }

    def to_python(self, value):
        return value


    def __init__(self, *args, **kwargs):
        pin_url_check = kwargs.pop('pin_url_check', None)
        signature = kwargs.pop('signature', None)

        super(PinField, self).__init__(*args, **kwargs)

        if pin_url_check is not None:
            self.pin_url_check = pin_url_check
        else:
            raise forms.ValidationError("required argument pin_url_check")

        if signature is not None:
            self.signature = signature
        else:
            raise forms.ValidationError("required argument signature")


    def validate(self, value):
        #if value is None :
        #raise ValidationError(self.default_error_messages['not_an_a'])
        url = self.pin_url_check + str(value)
        RawData = None
        try:
            RawData = urllib2.urlopen(url)
            data = json.load(RawData)
            if data["status"]:
                self.value = data["result"]
            return True
        except:
            raise ValidationError(self.default_error_messages['not_an_a'])


def get_hours_delta(Delta):
    td = Delta
    Seconds = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10 ** 6) / 10 ** 6
    return math.floor(Seconds / 3600)


class MyFinanceForms(forms.Form):
    def check_holds(self):
        diff = 0
        #try :
        Holds = HoldsWithdraw.objects.filter(user=self.__user).order_by('-id')[0]

        before = Holds.pub_date
        after = datetime.now()
        Delta = after - before
        hours = get_hours_delta(Delta)
        check = False
        if hours < Holds.hours:
            check = True
            diff = Holds.hours - hours
        else:
            check = False

        if check:
            raise forms.ValidationError(_(u"Установлен холд на вывод средств {hours} часов").format(hours=str(diff)))

    def check_funds(self):
        check = False
        try:
            amnt = Decimal(self.cleaned_data.get('amnt'))
        except:
            return False


        ## we must got mail
        Account = get_account(currency=self.currency_instance, user=self.__user)

        if Account.get_balance < amnt:
            check = True
        else:
            self.__balance = Account.get_balance
            check = False

        if check:
            raise forms.ValidationError(_(u"Недостаточно средств"))


    def check_funds_crypto(self):

        check = False
        try:
            amnt = Decimal(self.cleaned_data.get('amnt'))
        except:
            return False

        number_dec = str(amnt - int(amnt))[2:]
        if len(number_dec) > 8:
            check = True

        if check:
            raise forms.ValidationError(
                _(u"Операции с криптовалютами  возможны только с суммами до 8-ого знака после запятой"))

        TradePair = TradePairs.objects.get(currency_on=self.currency_instance,
                                           currency_from=self.currency_instance)
        self.comission = TradePair.min_trade_base

        if amnt < (self.comission * 2):
            raise forms.ValidationError(_(u"Недостаточно средств для совершения транзакции,\n\
минимальная сумма должна быть больше {comission} ").format(comission=str(self.comission * 2)))


    def check_funds_ussual(self):
        check = False
        try:
            amnt = Decimal(self.cleaned_data.get('amnt'))
        except:
            return False

        number_dec = str(amnt - int(amnt))[2:]
        if len(number_dec) > 2:
            check = True

        if check:
            raise forms.ValidationError(_(u"Операции  возможны только с суммами до 2-ого знака после запятой"))

    def clean(self):
        cleaned_data = super(MyFinanceForms, self).clean()
        Title = self.cleaned_data.get('currency', None)
        check = False
        try:
            self.currency_instance = Currency.objects.get(title=Title)
            check = False
        except:
            check = True

        if check:
            raise forms.ValidationError(_(u"Не удалось определить валюту"))

        return cleaned_data


    def check_currency_uah(self):

        check = False
        try:
            Title = self.cleaned_data.get('currency')
            if Title != "UAH":
                check = True
            else:
                check = False
        except:
            check = True

        if check:
            raise forms.ValidationError(_(u" Поддерживаем  переводы в  только гривне"))

    def __init__(self, *args, **kwargs):
        self.__user = kwargs.pop('user', None)

        super(MyFinanceForms, self).__init__(*args, **kwargs)

        for k, field in self.fields.items():
            if 'required' in field.error_messages:
                field.error_messages['required'] = _(u" '{field_name}' обязательное поле для заполнения").format(
                    field_name=field.label)
            field.widget.attrs['class'] = 'col-sm-5 form-control'


class CardP2PTransfersForm(MyFinanceForms):
    CardNumber = forms.CharField(max_length=100, required=True, label=_(u"Номер карты"),
                                 widget=forms.TextInput(attrs={'placeholder': _(u'Номер карты')}))

    CardName = forms.CharField(max_length=100, required=True, label=_(u"Имя и фамилия держателя карты"),
                               widget=forms.TextInput(attrs={'placeholder': _(u"Имя и фамилия держателя карты")}))
    amnt = forms.DecimalField(required=True,
                              widget=forms.TextInput(attrs={'placeholder': _(u'сумма')}),
                              label=_(u"Сумма (мин 10 ГРН) "), min_value=10)
    Agree = forms.BooleanField(required=True, label=_(u"Я согласен с балансом и не имею претензий к сервису"), )

    currency = forms.CharField(required=True,
                               widget=forms.HiddenInput()
    )


    def clean(self):
        self.cleaned_data = super(CardP2PTransfersForm, self).clean()
        self.check_currency_uah()
        self.check_funds()
        self.check_holds()
        return self.cleaned_data


class BankP2PForm(MyFinanceForms):
    account = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': _(u'номер счета')}),
                              label=_(u"Номер Счета"))
    amnt = forms.DecimalField(required=True,
                              widget=forms.TextInput(attrs={'placeholder': _(u'сумма')}),
                              label=_(u"Сумма"), min_value=500)
    description = forms.CharField(required=True,
                                  label=_(u"Получатель"))

    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        self.cleaned_data = super(BankP2PForm, self).clean()
        self.check_funds_ussual()
        self.check_funds()
        self.check_holds()
        return self.cleaned_data


class BankTransferForm(MyFinanceForms):
    mfo = forms.CharField(max_length=100, required=True, label=_(u"МФО Банка"),
                          widget=forms.TextInput(attrs={'placeholder': _(u'МФО')}))
    okpo = forms.CharField(required=True, label=_(u"ОКПО"),
                           widget=forms.TextInput(attrs={'placeholder': _(u'ОКПО')}))
    account = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': _(u'номер счета')}),
                              label=_(u"Номер Счета"))
    amnt = forms.DecimalField(required=True,
                              widget=forms.TextInput(attrs={'placeholder': _(u'сумма')}),
                              label=_(u"Сумма (мин 500 ГРН)"), min_value=500)
    currency = forms.CharField(required=True,
                               widget=forms.TextInput(attrs={'placeholder': _(u'валюта')}),
                               label=_(u"Валюта"))
    description = forms.CharField(required=True,
                                  label=_(u"Получатель"))

    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        self.cleaned_data = super(BankTransferForm, self).clean()
        self.check_currency_uah()
        self.check_funds_ussual()
        self.check_funds()
        self.check_holds()
        return self.cleaned_data


class CurrencyTransferForm(MyFinanceForms):
    wallet = forms.CharField(max_length=120, label=_(u"Кошелек"))
    amnt = forms.DecimalField(required=True, widget=forms.TextInput(attrs={'placeholder': _(u'сумма')}),
                              label=_(u"Сумма"),
                              min_value=0.00099)
    currency = forms.CharField(max_length=10, widget=forms.HiddenInput())
    Agree = forms.BooleanField(required=True, label=_(u"Я согласен с балансом и не имею претензий к сервису"), )
    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        self.cleaned_data = super(CurrencyTransferForm, self).clean()
        self.check_funds()
        self.check_holds()

        self.check_funds_crypto()
        return self.cleaned_data


class FiatCurrencyTransferForm(MyFinanceForms):
    wallet = forms.CharField(max_length=120, label=_(u"Счет в системе"))
    amnt = forms.DecimalField(required=True, widget=forms.TextInput(attrs={'placeholder': _(u'сумма')}),
                              label=_(u"Сумма"),
                              min_value=0.001)
    currency = forms.CharField(max_length=10, widget=forms.HiddenInput())
    Agree = forms.BooleanField(required=True, label=_(u"Я согласен с балансом и не имею претензий к сервису"), )
    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        self.cleaned_data = super(FiatCurrencyTransferForm, self).clean()
        self.check_funds()
        self.check_holds()
        return self.cleaned_data


class PinForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.__user = kwargs.pop('user', None)
        super(PinForm, self).__init__(*args, **kwargs)

        for k, field in self.fields.items():
            if 'required' in field.error_messages:
                field.error_messages['required'] = _(u" '{field}' обязательное поле для заполнения").format(
                    field=field.label)
            field.widget.attrs['class'] = 'col-sm-5 form-control'

    def check_pin(self):
        CheckPin = None
        try:
            CheckPin = self.fields["pin"].value
        except:
            raise forms.ValidationError(_(u"Вы неправильно ввели PIN-код "))

        Pin = None
        try:
            Pin = PinsImages.objects.get(user=self.__user)
        except PinsImages.DoesNotExist:
            raise forms.ValidationError(_(u"Обратитесь в службу поддержки, что бы получить pin-код для вывода "))

        CheckValue = generate_key_from(CheckPin, settings.PIN_SALT)
        if Pin.hash_value != CheckValue:
            raise forms.ValidationError(_(u"Вы неправильно ввели PIN-код "))

    key_type = forms.CharField(max_length=100, label=u"Kеу")

    key = forms.CharField(max_length=100, label=u"Kеу")

    pin = PinField(label=u"PIN", required=True,
                   pin_url_check=settings.PIN_URL_CHECK,
                   signature=settings.PIN_SIGNATURE
    )

    def clean(self):
        self.cleaned_data = super(PinForm, self).clean()

        self.check_pin()

        return self.cleaned_data


class LiqPayTransferForm(MyFinanceForms):
    phone = forms.CharField(max_length=100, label=_(u"Телефон акаунта в системе LiqPay"))
    amnt = forms.DecimalField(required=True, widget=forms.TextInput(attrs={'placeholder': _(u'сумма')}),
                              label=_(u"Сумма (мин 100 ГРН)"), min_value=100)
    currency = forms.CharField(required=True, widget=forms.TextInput(attrs={'placeholder': _(u'валюта')}),
                               label=_(u"Валюта")
    )

    description = forms.CharField(required=True,
                                  label=_(u"получатель"))
    Agree = forms.BooleanField(required=True, label=_(u"Я согласен с балансом и не имею претензий к сервису"), )

    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        self.cleaned_data = super(LiqPayTransferForm, self).clean()
        self.check_currency_uah()
        self.check_funds_ussual()
        self.check_funds()
        self.check_holds()
        return self.cleaned_data
    
           
