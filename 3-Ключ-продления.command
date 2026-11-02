#!/bin/zsh
# Сохраняет ключ GitHub (github_pat_...) в секрет GH_PAT — нужен, чтобы токен Instagram продлевался сам
cd ~/REELS/рейтинги || exit 1
echo "Вставь ключ GitHub (начинается с github_pat_) и нажми Enter."
echo "Символы при вставке не видны — это нормально."
bin/gh secret set GH_PAT || exit 1
echo
bin/gh secret list
echo "Готово — можно закрыть окно."
