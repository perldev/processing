from django.core import mail
import crypton.settings_mail as settings


def subscribe_connection():
    Host = settings.SUBSCRIBE_HOST
    User = settings.SUBSCRIBE_USER
    Port = settings.SUBSCRIBE_PORT
    Pwd = settings.SUBSCRIBE_PWD
    my_use_tls = settings.SUBSCRIBE_TLS
    return mail.get_connection(
        host=Host,
        port=Port,
        username=User,
        password=Pwd,
        user_tls=my_use_tls
    )

           
