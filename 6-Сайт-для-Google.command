#!/bin/zsh
# Создаёт маленький ОТКРЫТЫЙ репозиторий world-in-numbers-site с тремя страницами (главная, политика конфиденциальности,
# условия) и включает GitHub Pages — эти ссылки нужны Google, чтобы опубликовать приложение для YouTube.
cd ~/REELS/рейтинги || exit 1
GH=$PWD/bin/gh
TMP=$(mktemp -d)
cp site/*.html "$TMP"/ && cd "$TMP" || exit 1
git init -q -b main && git add . && git -c user.name=ajdaha779-cmd -c user.email=ajdaha779-cmd@users.noreply.github.com commit -qm "Site" || exit 1
$GH repo create world-in-numbers-site --public --source=. --push || exit 1
$GH api -X POST repos/ajdaha779-cmd/world-in-numbers-site/pages -f "source[branch]=main" -f "source[path]=/" >/dev/null || exit 1
echo
echo "Готово! Через 1–2 минуты страницы будут доступны:"
echo "  https://ajdaha779-cmd.github.io/world-in-numbers-site/"
echo "  https://ajdaha779-cmd.github.io/world-in-numbers-site/privacy.html"
echo "  https://ajdaha779-cmd.github.io/world-in-numbers-site/terms.html"
echo "Можно закрыть окно."
