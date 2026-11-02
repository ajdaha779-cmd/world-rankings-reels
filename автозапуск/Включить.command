#!/bin/zsh
# Каждую субботу в 09:00 Mac сам делает пачку из 14 роликов (если Mac спал — сделает при пробуждении)
cp "/Users/ajdaha/REELS/рейтинги/автозапуск/com.ajdaha.reitingi.plist" ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.ajdaha.reitingi.plist && echo "Автозапуск включён: суббота 09:00"
