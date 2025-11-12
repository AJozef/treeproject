"""Главный файл маршрутов (urls) проекта: определяет пути и шаблоны страниц."""

from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="index.html"), name="index"),
    path("about/", TemplateView.as_view(template_name="about.html"), name="about"),
    path("blog/", TemplateView.as_view(template_name="blog.html"), name="blog"),
    path("blog/categories/",
         TemplateView.as_view(template_name="blog_categories.html"),
         name="blog_categories"),
    path("blog/categories/1/",
         TemplateView.as_view(template_name="category_1.html"),
         name="blog_category_1"),
    path("blog/categories/2/",
         TemplateView.as_view(template_name="category_2.html"),
         name="blog_category_2"),
    path("blog/categories/3/",
         TemplateView.as_view(template_name="category_3.html"),
         name="blog_category_3"),
]
