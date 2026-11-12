#!/bin/zsh
# Сохраняет ключ YouTube Data API (начинается с AIza) — чтобы читать комментарии под роликами YouTube для карты.
# Ключ только для чтения публичных данных. Хранится на этом Mac (data/youtube_key.txt) и в секрете GitHub YT_API_KEY.
cd ~/REELS/рейтинги || exit 1
echo "Вставь ключ YouTube (начинается с AIza) и нажми Enter."
echo "Символы при вставке не видны — это нормально."
read -rs KEY
echo
case "$KEY" in AIza*) ;; *) echo "Это не похоже на ключ YouTube (должен начинаться с AIza). Попробуй ещё раз."; exit 1;; esac
umask 077
print -rn -- "$KEY" > data/youtube_key.txt
print -rn -- "$KEY" | bin/gh secret set YT_API_KEY || exit 1
echo
bin/gh secret list
echo "Готово — можно закрыть окно."
