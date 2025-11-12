"""Модели меню и пунктов меню для приложения tree_menu."""

from django.core.exceptions import ValidationError
from django.db import models

class Menu(models.Model):
    """Модель меню: содержит системное имя и заголовок для админки."""

    name = models.SlugField("Системное имя", unique=True, help_text="Например: main_menu")
    title = models.CharField("Заголовок (для админки)", max_length=200, blank=True)

    class Meta:
        """Метаданные модели Menu."""
        verbose_name = "Меню"
        verbose_name_plural = "Меню"

    def __str__(self):
        """Возвращает название меню (title или name)."""
        return self.title or self.name

class MenuItem(models.Model):
    """Пункт меню: может ссылаться на URL или Named URL, поддерживает иерархию."""

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items", verbose_name="Меню")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children", null=True, blank=True, verbose_name="Родитель"
    )
    title = models.CharField("Текст пункта", max_length=200)
    url = models.CharField("Явный URL", max_length=500, blank=True)
    named_url = models.CharField("Named URL", max_length=200, blank=True)
    sort_order = models.IntegerField("Порядок", default=0)

    class Meta:
        """Метаданные модели MenuItem."""
        verbose_name = "Пункт меню"
        verbose_name_plural = "Пункты меню"
        ordering = ("sort_order", "id")

    def __str__(self):
        """Возвращает текст пункта меню."""
        return self.title

    def clean(self):
        """Проверяет корректность заполнения полей URL и родителя."""

        if bool(self.url) == bool(self.named_url):
            raise ValidationError("Укажи либо 'Явный URL', либо 'Named URL', но не оба.")
        if self.parent and self.parent.menu_id != self.menu_id:
            raise ValidationError("Родитель должен принадлежать тому же меню.")
