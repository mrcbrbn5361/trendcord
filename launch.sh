#!/data/data/com.termux/files/usr/bin/bash
cd /data/data/com.termux/files/home/trendcord
setsid venv/bin/python main.py >> logs/bot.log 2>&1 &
echo $!
