#!/bin/sh
kill `cat /home/btc_trade/crypton/manage.pid`
cd /home/btc_trade/crypton
/usr/bin/python /home/btc_trade/crypton/manage.py runfcgi host=127.0.0.1 port=8366 pidfile=/home/btc_trade/crypton/manage.pid daemonize=true maxspare=10
