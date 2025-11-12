"""Конфигурация приложения tree_menu."""

from django.apps import AppConfig


class TreeMenuConfig(AppConfig):
    """Настройки приложения Tree Menu для панели администратора Django."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "tree_menu"
    verbose_name = "Tree Menu"
