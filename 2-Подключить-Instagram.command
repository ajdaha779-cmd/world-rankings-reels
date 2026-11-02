#!/bin/zsh
# Проверяет токен Instagram и кладёт его в секреты GitHub (токен никуда больше не уходит)
cd ~/REELS/рейтинги || exit 1
.venv/bin/python instagram.py setup || exit 1
.venv/bin/python -c "import json;print(json.load(open('data/instagram.json'))['token'],end='')" | bin/gh secret set IG_TOKEN
.venv/bin/python -c "import json;print(json.load(open('data/instagram.json'))['user_id'],end='')" | bin/gh secret set IG_USER_ID
echo
bin/gh secret list
echo "Готово — можно закрыть окно и написать Claude."
