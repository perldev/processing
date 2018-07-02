# -*- coding: utf-8 -*-
import crypton.settings

PN = crypton.settings.PROJECT_NAME
__author__ = 'bogdan'
from django.utils.translation import ugettext as _

secondary_main_forgot_link = _(u'Восстановление пароля')
forgot_link_not_found_msg = _(u'Увы! Указанная ссылка для восстановления  не найдена ')
forgot_main_update = _(u'Обновить пароль')
forgot_main_help_text = _(u"Введите новый пароль в форме ниже")
reset_pwd_success = _(u"Пароль вашей учетной записи удачно изменен, теперь можете авторизоваться с новыми данными")

pin_confirm_operation_title = _(u"Введите персональный PIN, для подтверждения операции")

pin_reset_form_title = _(u"Для получения нового PIN-а, введите текущий")
help_page = _(u"Помощь")
pin_page = _(u"Страница персонального PIN кода")
pagetitle_main = _(PN)
pagetitle_home = _(u"самый простой и дешевый способ купить или продать биткоины в Украине")
withdraw_cancel = _(u"Вывод отменен")
withdraw_msg_cancel = _(u"Ваша заявка на вывод отменена, мы рады, что вы остаетесь с нами")

secondary_main = _(u"BTC TRADE UA украинская биржа криптовалют")
secondary_regis = _(u"Регистрация")
secondary_regis_success = _(u"Регистрация прошла успешно")
secondary_regis_finish_success = _(u"Вы успешно активировали свой акаунт")
secondary_regis_finish_error = _(u"Ссылка активации не активна")
secondary_main_forgot = _(u"Восстановление пароля")
reset_password_title = _(u"Сбросить пароль")
common_help_text = _(u"Внимание, при сбросе пароля устанавливается hold вывода средств на 36 часов")
forgot_sending_email_msg = _(u"На указаный электронный адрес было выслано письмо с новыми данными для авторизации")
withdraw_transfer = _(u"Отправить")
attention_be_aware = _(u"Будьте внимательны при заполнение реквизитов<br/> \n\
комиссия согласно условиям вашего банка")
withdraw_title_bank = _(u"Заявка на вывод банковским переводом")
withdraw_title_liqpay = _(u"Заявка на вывод через систему liqpay")
liqpay_attention_be_aware = _(u"Будьте внимательны при указание номера счета liqpay")
withdrawing_secondary_main_email_confirmation_title = _(u"Подтверждение по электронной почте")
withdrawing_sending_email_confirmation = _(
    u"Код для подтверждения вывода средств был направлен вам на электронный адрес")

withdrawing_error = _(u"Ошибка подтверждения")
withdraw_doesnot_existed = _(u"Вывод с таким кодом не найден, либо уже в работе, уточняйте вопрос  у службы поддержки")
withdraw_ok = _(u"Вывод подтвержден")
withdraw_msg_ok = _(u"Ваша заявка на вывод подтверждена, перевод будет осуществлен в ближайшее время")
p2p_transfer = _(u"Отправить")
emoney_transfer = _(u"Отправить")
emoney_attention_be_aware = _(u"Будьте внимательны при заполении реквизитов")

p2p_attention_be_aware = _(u"Будьте внимательны при заполении реквизитов,<br/>\n\
комиссия для вывода на Карту ПриватБанка 1&nbsp;%,<br/>\n\
Карта украинского банка 1.3&nbsp;%,<br/>\n\
Карта зарубежного банка 1,95 дол + 1&nbsp;%<br/>\n\
")
attention_be_aware_crypto = _(u"Будьте внимательны при заполении реквизитов,<br/>\n\
комиссия системы данной криптовалюты составляет %s&nbsp;<br/>\n\
")
pin_change_title = _(u"Смена PIN-кода")
