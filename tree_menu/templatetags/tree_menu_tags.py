"""Шаблонные теги и утилиты для построения древовидного меню."""

from collections import defaultdict
from django import template
from django.urls import reverse, NoReverseMatch
from django.template.loader import render_to_string
from tree_menu.models import MenuItem

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Позволяет безопасно получать значение из словаря в шаблоне.
    Использование: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


def _normalize_path(path: str) -> str:
    """Приводит URL-путь к каноническому виду."""
    if not path:
        return "/"

    if path.startswith(("http://", "https://", "#")):
        return path

    if not path.startswith("/"):
        path = "/" + path

    if path != "/" and not path.endswith("/"):
        path = path + "/"

    return path

def _resolve_url(named: str | None, raw: str | None):
    """Преобразует 'named_url' или 'url' пункта меню в конечный URL."""
    if named:
        try:
            return reverse(named)
        except NoReverseMatch:
            return "#"
    return raw or "#"

@register.simple_tag(takes_context=True)
def draw_menu(context, menu_name: str):
    """
    Готовит данные для древовидного меню и рендерит их через HTML-шаблон.

    Выполняет ровно 1 запрос к БД.
    Логика работы:
    1.  Получает все MenuItem, относящиеся к `menu_name`. (1 запрос)
    2.  Определяет `current_path` (текущий URL) из 'request' в контексте.
    3.  Преобразует 'url' и 'named_url' в итоговые `resolved_url`.
    4.  Строит два словаря:
        - `by_id`: для быстрого доступа к пункту по его ID.
        - `children`: defaultdict(list) для хранения дочерних ID.
    5.  Находит `active_id` — ID пункта, чей `norm_url` совпадает с `current_path`.
    6.  Находит `expanded` (set) — ID всех пунктов, которые должны быть раскрыты.
    7.  Передает все эти данные в шаблон "tree_menu/menu.html" для отрисовки.
    """
    request = context.get("request")
    current_path = _normalize_path(getattr(request, "path", "/"))

    # Шаг 1: 1 запрос к БД
    items = list(
        MenuItem.objects.filter(menu__name=menu_name).values(
            "id", "parent_id", "title", "url", "named_url", "sort_order"
        ).order_by("sort_order", "id")
    )
    if not items:
        return ""

    # Шаги 2-4: Обработка данных в Python
    for it in items:
        it["resolved_url"] = _resolve_url(it["named_url"], it["url"])
        it["norm_url"] = _normalize_path(it["resolved_url"])

    by_id = {it["id"]: it for it in items}
    children = defaultdict(list)
    roots = []
    for it in items:
        (children[it["parent_id"]].append(it["id"])
         if it["parent_id"]
         else roots.append(it["id"]))

    # Шаг 5: Поиск активного пункта
    active_id = None
    max_len = 0
    for it in items:
        if not it["norm_url"].startswith("/"):
            continue

        norm_url = it["norm_url"]

        if norm_url == "/" and current_path != "/":
            continue

        if current_path.startswith(norm_url):
            current_len = len(norm_url)
            if current_len > max_len:
                max_len = current_len
                active_id = it["id"]

    # Шаг 6: Поиск раскрытых пунктов
    expanded = set()
    if active_id:
        cur = active_id
        while cur:
            expanded.add(cur)
            cur = by_id[cur]["parent_id"]

    # Шаг 7: Передача данных в шаблон
    menu_context = {
        "menu_name": menu_name,
        "items_by_id": by_id,
        "root_items": [by_id[rid] for rid in roots],
        "children_map": children,
        "active_id": active_id,
        "expanded_ids": expanded,
        "request": request,
    }

    return render_to_string("tree_menu/menu.html", menu_context)