#!/bin/sh
kill `cat /home/btc_trade/crypton/manage_api.pid`
cd /home/btc_trade/crypton
python ./manage.py runfcgi host=127.0.0.1 port=8367 daemonize=true maxspare=2 pidfile=/home/btc_trade/crypton/manage_api.pid
