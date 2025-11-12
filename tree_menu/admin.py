"""Админка для древовидного меню: регистрация моделей и инлайнов."""

from django.contrib import admin
from django.http import HttpRequest
from .models import Menu, MenuItem


class MenuItemInline(admin.TabularInline):
    """Инлайн для пунктов меню внутри формы Menu."""
    model = MenuItem
    extra = 1
    fields = ("title", "parent", "url", "named_url", "sort_order")
    ordering = ("sort_order", "id")

    def formfield_for_foreignkey(self, db_field, request: HttpRequest, **kwargs):
        """
        Ограничивает список вариантов поля parent пунктами текущего меню.

        В change-вью Menu в URL есть object_id. Берём его из resolver_match,
        и если нашли — фильтруем queryset для parent по этому menu_id.
        """
        if db_field.name == "parent":
            resolver_match = getattr(request, "resolver_match", None)
            menu_id = None
            if resolver_match and getattr(resolver_match, "kwargs", None):
                menu_id = resolver_match.kwargs.get("object_id")

            if menu_id:
                kwargs["queryset"] = MenuItem.objects.filter(menu_id=menu_id)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    """Админ-настройки для Menu."""
    list_display = ("name", "title")
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    """Админ-настройки для MenuItem."""
    list_display = ("title", "menu", "parent", "sort_order")
    list_filter = ("menu",)
    search_fields = ("title", "url", "named_url")
    ordering = ("menu", "sort_order", "id")
