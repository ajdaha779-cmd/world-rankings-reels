#!/bin/zsh
# Создаёт ПРИВАТНЫЙ репозиторий world-rankings-reels и загружает туда код
cd ~/REELS/рейтинги || exit 1
if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin main
else
  bin/gh repo create world-rankings-reels --private --source . --remote origin --push
fi
echo
bin/gh repo view --json url,visibility -q '"Репозиторий: " + .url + "  (" + .visibility + ")"'
echo "Готово — можно закрыть окно."
