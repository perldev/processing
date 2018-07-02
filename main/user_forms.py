# -*- coding: utf-8 -*-


from django.utils.translation import ugettext as _

from django import forms
from captcha.fields import CaptchaField
import crypton.settings as settings
from main.finance_forms import PinField
import re
from django.contrib.auth.models import User
from main.models import PinsImages
from main.http_common import generate_key_from


class PinChangeForm(forms.Form):
    pin = PinField(
        label=u"Введите старый PIN-код",
        required=True,
        pin_url_check=settings.PIN_URL_CHECK,
        signature=settings.PIN_SIGNATURE
    )

    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
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

        if Pin.hash_value != generate_key_from(CheckPin, settings.PIN_SALT):
            raise forms.ValidationError(_(u"Вы неправильно ввели PIN-код "))

        return self.cleaned_data


    def __init__(self, *args, **kwargs):
        self.__user = kwargs.pop('user', None)
        super(PinChangeForm, self).__init__(*args, **kwargs)
        for k, field in self.fields.items():
            if 'required' in field.error_messages:
                field.error_messages['required'] = _(u'Это обязательное поле для заполнения')
            field.widget.attrs['class'] = 'col-sm-5 form-control'


class UsersForgotLinkPswd(forms.Form):
    password1 = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'placeholder': 'password'}),
                                label=_(u"Новый пароль"))
    password2 = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'placeholder': 'confirm password'}),
                                label=_(u"Подтвердите пароль"))

    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password1 != password2:
            raise forms.ValidationError(_(u"Пароли не совпадают"))

        return self.cleaned_data


    def __init__(self, *args, **kwargs):
        super(UsersForgotLinkPswd, self).__init__(*args, **kwargs)
        for k, field in self.fields.items():
            if 'required' in field.error_messages:
                field.error_messages['required'] = _(u'Это обязательное поле для заполнения')
            field.widget.attrs['class'] = 'col-sm-5 form-control'


class UsersForgotMail(forms.Form):
    email = forms.EmailField(required=True,
                             label=_(u"Укажите адрес электронной почты, указанный при регистрации"),
                             widget=forms.TextInput(attrs={'placeholder': 'email'}))
    captcha = CaptchaField(label=u"Пожалуйста, введите  код с картинки")
    error_css_class = 'error'
    required_css_class = 'required'

    def __init__(self, *args, **kwargs):
        super(UsersForgotMail, self).__init__(*args, **kwargs)
        self.user = None
        for k, field in self.fields.items():
            if 'required' in field.error_messages:
                field.error_messages['required'] = _(u'Это обязательное поле для заполнения')
            field.widget.attrs['class'] = 'col-sm-5 form-control'


    def clean(self):

        email = self.cleaned_data.get('email')
        check = False
        try:
            user_obj = User.objects.get(email=email)
            self.user = user_obj
            check = False
        except:
            check = True

        if check:
            raise forms.ValidationError(_(u"Пользователь с такой электронной почтой не  зарегистрирован :("))

        return self.cleaned_data


class UsersRegis(forms.Form):
    username = forms.CharField(
        max_length=100, label=_(u"Login пользователя"),
        widget=forms.TextInput(attrs={'placeholder': 'username'}),
    )
    email = forms.EmailField(required=True, label=_(u"Адрес электронной почты"),
                             widget=forms.TextInput(attrs={'placeholder': 'email'}))
    password1 = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'placeholder': 'password'}),
                                label=_(u"Пароль"))
    password2 = forms.CharField(required=True, widget=forms.PasswordInput(attrs={'placeholder': 'confirm password'}),
                                label=_(u"Подтверждение пароля"))

    # captcha = CaptchaField(label = u"Введите пожайлуста код с картинки" )

    reference = forms.CharField(required=False, widget=forms.HiddenInput())

    agreement = forms.BooleanField(required=True, label=_(u"Я согласен с пользовательским соглашением"))

    error_css_class = 'error'
    required_css_class = 'required'

    def clean(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password1 != password2:
            raise forms.ValidationError(_(u"Пароли не совпадают"))

        username = self.cleaned_data.get('username', "")
        check = False

        try:
            T = User.objects.get(username=username)
            check = True
        except:
            pass

        if check:
            raise forms.ValidationError(_(u"Пользователь с таким именем уже зарегистрирован :("))

        match = re.search("^[A-Za-z\d]+$", username)

        if not match:
            raise forms.ValidationError(
                _(u"В имени пользователя допускаются только символы латинского алфавита и цифры :("))

        email = self.cleaned_data.get('email')

        try:
            User.objects.get(email=email)
            check = True
        except:
            pass

        if check:
            raise forms.ValidationError(_(u"Пользователь с такой электронной почтой  уже зарегистрирован :("))

        return self.cleaned_data


    def __init__(self, *args, **kwargs):
        super(UsersRegis, self).__init__(*args, **kwargs)
        for k, field in self.fields.items():
            if 'required' in field.error_messages:
                field.error_messages['required'] = _(u'Это обязательное поле для заполнения')

            if 'required' in field.error_messages and k == "agreement":
                field.error_messages['required'] = _(u'Вы должны подтвердить пользовательское соглашение')

            if 'required' in field.error_messages and k == "username":
                field.error_messages['required'] = _(u'Имя пользователя будет использоваться для входа в систему')

            if k <> "agreement":
                field.widget.attrs['class'] = 'col-sm-5 form-control'
