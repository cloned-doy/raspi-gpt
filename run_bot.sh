#!/bin/bash

# activate virtual environment and run Python script
workon gpt
python ./gpt-app/xserver.py &

# wait for 5 seconds
sleep 5

# run Golang server
# cd /path/to/Golang/server
./gpt-app/go-whatsapp &

sleep 10

# schedule send_log.sh to run regularly using cron
(crontab -l ; echo "*/11 * * * * /home/pi/send_log.sh") | crontab -