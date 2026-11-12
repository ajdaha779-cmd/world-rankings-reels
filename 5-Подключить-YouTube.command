#!/bin/zsh
# Одноразово подключает канал YouTube для автозагрузки (окно входа Google). Перед запуском скачай client_secret_….json в «Загрузки».
cd ~/REELS/рейтинги || exit 1
.venv/bin/python tools/youtube_auth.py
