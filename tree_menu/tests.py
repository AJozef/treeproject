"""Набор тестов для моделей, утилит и шаблонных тегов приложения tree_menu."""

import re
from django.test import TestCase, SimpleTestCase, RequestFactory
from django.template import Template, Context
from django.core.exceptions import ValidationError
from django.urls import reverse

from .models import Menu, MenuItem
from .templatetags.tree_menu_tags import _normalize_path, _resolve_url


# =============================================================================
# 1. Тесты для models.py
# =============================================================================

class MenuItemValidationTests(TestCase):
    """
    Тестирование валидации и методов моделей Menu и MenuItem.
    """

    @classmethod
    def setUpTestData(cls):
        """Создание данных для TestCase."""
        cls.menu1 = Menu.objects.create(name="main_menu", title="Главное меню")
        cls.menu2 = Menu.objects.create(name="footer_menu", title="Нижнее меню")

        cls.parent_item = MenuItem.objects.create(
            menu=cls.menu1,
            title="Родитель",
            named_url="index",
            sort_order=10
        )

    def test_menu_str_method(self):
        """Проверка, что __str__ для Menu возвращает title или name."""
        menu_with_title = Menu(name="menu1", title="Меню с заголовком")
        menu_no_title = Menu(name="menu2", title="")
        self.assertEqual(str(menu_with_title), "Меню с заголовком")
        self.assertEqual(str(menu_no_title), "menu2")

    def test_menu_item_str_method(self):
        """Проверка, что __str__ для MenuItem возвращает title."""
        item = MenuItem(title="Тестовый пункт")
        self.assertEqual(str(item), "Тестовый пункт")

    def test_clean_url_and_named_url_exclusive(self):
        """
        Тест: MenuItem.clean() должен вызывать ValidationError,
        если 'url' и 'named_url' заданы одновременно или не заданы оба.
        """

        # Случай 1: Оба заданы
        item_both = MenuItem(
            menu=self.menu1,
            title="Ошибка (оба)",
            url="/test/",
            named_url="index"
        )
        with self.assertRaisesMessage(ValidationError, "Укажи либо 'Явный URL', либо 'Named URL', но не оба."):
            item_both.clean()

        # Случай 2: Ни один не задан
        item_none = MenuItem(
            menu=self.menu1,
            title="Ошибка (ни один)",
            url="",
            named_url=""
        )
        with self.assertRaisesMessage(ValidationError, "Укажи либо 'Явный URL', либо 'Named URL', но не оба."):
            item_none.clean()

        # Случай 3: Только 'url' (Корректно)
        item_url_only = MenuItem(
            menu=self.menu1,
            title="Только URL",
            url="/test/",
            named_url=""
        )
        try:
            item_url_only.clean()
        except ValidationError:
            self.fail("clean() вызвал ValidationError необоснованно (только для URL)")

        # Случай 4: Только 'named_url' (Корректно)
        item_named_only = MenuItem(
            menu=self.menu1,
            title="Только Named URL",
            url="",
            named_url="index"
        )
        try:
            item_named_only.clean()
        except ValidationError:
            self.fail("clean() вызвал ValidationError необоснованно (только для Named URL)")

    def test_clean_parent_must_be_in_same_menu(self):
        """
        Тест: MenuItem.clean() должен вызывать ValidationError,
        если родитель ('parent') принадлежит другому меню.
        """

        # Случай 1: Родитель из другого меню (Ошибка)
        child_item_wrong_menu = MenuItem(
            menu=self.menu2,
            parent=self.parent_item,
            title="Дочерний (ошибка)",
            named_url="about"
        )
        with self.assertRaisesMessage(ValidationError, "Родитель должен принадлежать тому же меню."):
            child_item_wrong_menu.clean()

        # Случай 2: Родитель из того же меню (Корректно)
        child_item_ok = MenuItem(
            menu=self.menu1,
            parent=self.parent_item,
            title="Дочерний (ОК)",
            named_url="about"
        )
        try:
            child_item_ok.clean()
        except ValidationError:
            self.fail("clean() вызвал ValidationError необоснованно (родитель из того же меню)")


# =============================================================================
# 2. Тесты для утилит в templatetags
# =============================================================================

class TemplateTagUtilsTests(SimpleTestCase):
    """
    Тестирование вспомогательных функций (утилит) из 'tree_menu_tags.py'.
    """

    def test_normalize_path(self):
        """Тестирование функции _normalize_path."""
        self.assertEqual(_normalize_path("/path/to/page/"), "/path/to/page/")
        self.assertEqual(_normalize_path("/path/to/page"), "/path/to/page/")
        self.assertEqual(_normalize_path("/"), "/")
        self.assertEqual(_normalize_path(""), "/")
        # Не-URL пути (например, '#') должны оставаться без изменений
        self.assertEqual(_normalize_path("#anchor"), "#anchor")
        self.assertEqual(_normalize_path("http://example.com"), "http://example.com")

    def test_resolve_url(self):
        """Тестирование функции _resolve_url."""

        # Случай 1: Корректный named_url
        # (Используем имена URL из 'treeproject/urls.py')
        self.assertEqual(_resolve_url("index", None), "/")
        self.assertEqual(_resolve_url("about", "/ignored/path"), "/about/")

        # Случай 2: Только явный (raw) URL
        self.assertEqual(_resolve_url(None, "/raw/path/"), "/raw/path/")

        # Случай 3: Ничего не задано
        self.assertEqual(_resolve_url(None, None), "#")
        self.assertEqual(_resolve_url("", ""), "#")

        # Случай 4: Ошибка NoReverseMatch (несуществующее имя)
        self.assertEqual(_resolve_url("non_existent_name", None), "#")

        # Случай 5: Явный URL, похожий на named_url
        self.assertEqual(_resolve_url(None, "not_a_name"), "not_a_name")


# =============================================================================
# 3. Интеграционные тесты для тега draw_menu
# =============================================================================

class DrawMenuIntegrationTests(TestCase):
    """
    Интеграционные тесты для шаблонного тега {% draw_menu %}.
    Проверяют логику раскрытия, определение активного пункта и
    требование о единственном запросе к БД.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Создаем тестовую структуру меню один раз для всех тестов класса.

        Структура:
        - Home (/)
        - Blog (/blog/)
          - Categories (/blog/categories/)
            - Category 1 (/blog/categories/1/)
        - About (/about/)
        - External (http://example.com)
        """
        cls.menu = Menu.objects.create(name="main_menu", title="Главное меню")

        cls.item_home = MenuItem.objects.create(
            menu=cls.menu, title="Home", named_url="index", sort_order=10
        )
        cls.item_blog = MenuItem.objects.create(
            menu=cls.menu, title="Blog", named_url="blog", sort_order=20
        )
        cls.item_about = MenuItem.objects.create(
            menu=cls.menu, title="About", named_url="about", sort_order=40
        )
        cls.item_ext = MenuItem.objects.create(
            menu=cls.menu, title="External", url="http://example.com", sort_order=50
        )

        cls.item_cats = MenuItem.objects.create(
            menu=cls.menu,
            title="Categories",
            named_url="blog_categories",
            parent=cls.item_blog,
            sort_order=1
        )

        cls.item_cat1 = MenuItem.objects.create(
            menu=cls.menu,
            title="Category 1",
            url="/blog/categories/1/",  # Явный URL для теста
            parent=cls.item_cats,
            sort_order=1
        )

        cls.menu2 = Menu.objects.create(name="footer_menu")
        MenuItem.objects.create(menu=cls.menu2, title="Footer Link", url="/footer")

    def setUp(self):
        """Настраиваем RequestFactory для каждого теста."""
        self.factory = RequestFactory()
        self.template_to_render = Template(
            "{% load tree_menu_tags %}{% draw_menu 'main_menu' %}"
        )

    def _render_template(self, path: str) -> str:
        """Хелпер для рендеринга шаблона с заданным request.path."""
        request = self.factory.get(path)
        context = Context({'request': request})
        return self.template_to_render.render(context)

    def test_draw_menu_uses_one_query(self):
        """Отрисовка меню должна выполнять ровно 1 запрос к БД."""
        with self.assertNumQueries(1):
            self._render_template(reverse("index"))

        with self.assertNumQueries(1):
            self._render_template(reverse("blog_categories"))

    def test_non_existent_menu_renders_nothing(self):
        """Тег не должен ничего возвращать, если имя меню не найдено."""
        template = Template("{% load tree_menu_tags %}{% draw_menu 'no_such_menu' %}")
        request = self.factory.get('/')
        context = Context({'request': request})

        with self.assertNumQueries(1):
            html = template.render(context)

        self.assertEqual(html.strip(), "")

    def test_menu_item_order(self):
        """Пункты меню должны рендериться в порядке 'sort_order'."""
        html = self._render_template(reverse("index"))

        pos_home = html.find("Home")
        pos_blog = html.find("Blog")
        pos_about = html.find("About")

        self.assertTrue(0 < pos_home < pos_blog < pos_about)

    def test_expansion_on_root_url(self):
        """
        На главной странице ("/") "Home" должен быть 'active' и 'expanded'.
        Остальные пункты не должны иметь классов.
        """
        html = self._render_template(reverse("index"))

        # 1. "Home" - активен и развернут
        expected_home = f'<li class="active expanded"><a href="{reverse("index")}">Home</a></li>'
        self.assertInHTML(expected_home, html)

        # 2. "Blog" - неактивен, не развернут
        expected_blog = f'<li><a href="{reverse("blog")}">Blog</a></li>'
        self.assertInHTML(expected_blog, html)

        # 3. "About" - неактивен, не развернут
        expected_about = f'<li><a href="{reverse("about")}">About</a></li>'
        self.assertInHTML(expected_about, html)

        # 4. Вложенные элементы не должны быть видны
        self.assertNotIn("Categories", html)

    def test_expansion_on_child_url(self):
        """
        На странице "/blog/"
        - "Home" неактивен.
        - "Blog" должен быть 'active' и 'expanded'.
        - "Categories" (1-й уровень потомков) должен быть отрисован.
        - "Category 1" (2-й уровень) не должен быть отрисован.
        """
        html = self._render_template(reverse("blog"))

        # "Blog" - активен и развернут
        blog_href = reverse("blog")
        # "Categories" (потомок) должен быть отрисован
        cats_href = reverse("blog_categories")

        expected_blog_html = f"""
        <li class="active expanded">
            <a href="{blog_href}">Blog</a>
            <ul>
                <li><a href="{cats_href}">Categories</a></li>
            </ul>
        </li>
        """
        self.assertInHTML(expected_blog_html, html)

        # "Home" неактивен
        expected_home = f'<li><a href="{reverse("index")}">Home</a></li>'
        self.assertInHTML(expected_home, html)

        # "Category 1" (внук) не должен быть виден
        self.assertNotIn("Category 1", html)

    def test_expansion_on_nested_url(self):
        """
        На странице "/blog/categories/"
        - "Blog" (родитель) должен быть 'expanded', но не 'active'.
        - "Categories" (активный) должен быть 'active' и 'expanded'.
        - "Category 1" (1-й уровень потомков) должен быть отрисован.
        """
        html = self._render_template(reverse("blog_categories"))

        blog_href = reverse("blog")
        cats_href = reverse("blog_categories")
        cat1_href = "/blog/categories/1/"

        # Ожидаем, что вся ветка "Blog" будет развернута
        expected_html_branch = f"""
        <li class="expanded">
            <a href="{blog_href}">Blog</a>
            <ul>
                <li class="active expanded">
                    <a href="{cats_href}">Categories</a>
                    <ul>
                        <li><a href="{cat1_href}">Category 1</a></li>
                    </ul>
                </li>
            </ul>
        </li>
        """
        self.assertInHTML(expected_html_branch, html)

        # "Home" неактивен
        expected_home = f'<li><a href="{reverse("index")}">Home</a></li>'
        self.assertInHTML(expected_home, html)

    def test_expansion_on_leaf_url(self):
        """
        На странице '/blog/categories/1/' активен ровно лист 'Category 1',
        его предки 'Categories' и 'Blog' имеют только 'expanded'.
        'Home' и 'About' — без классов.
        """
        html = self._render_template("/blog/categories/1/")

        blog_href = reverse("blog")
        cats_href = reverse("blog_categories")
        cat1_href = "/blog/categories/1/"

        # Ветка с предками должна быть раскрыта
        expected_branch = f"""
        <li class="expanded">
            <a href="{blog_href}">Blog</a>
            <ul>
                <li class="expanded">
                    <a href="{cats_href}">Categories</a>
                    <ul>
                        <li class="active expanded"><a href="{cat1_href}">Category 1</a></li>
                    </ul>
                </li>
            </ul>
        </li>
        """
        self.assertInHTML(expected_branch, html)

        self.assertInHTML(f'<li><a href="{reverse("index")}">Home</a></li>', html)
        self.assertInHTML(f'<li><a href="{reverse("about")}">About</a></li>', html)

    def test_only_one_active_item(self):
        """
        В любой отрисовке меню должен быть ровно один элемент с классом 'active'.
        Проверим на трех уровнях URL.
        """
        for path in [reverse("index"), reverse("blog"), reverse("blog_categories"), "/blog/categories/1/"]:
            html = self._render_template(path)
            active_hits = re.findall(r'class="[^"]*\bactive\b', html)
            self.assertEqual(len(active_hits), 1, msg=f"Должен быть ровно один .active для {path}")

    def test_ancestors_expanded_not_active_on_leaf(self):
        """
        На '/blog/categories/1/' предки ('Categories', 'Blog') должны иметь 'expanded' и
        не иметь 'active'.
        """
        html = self._render_template("/blog/categories/1/")

        blog_href = reverse("blog")
        cats_href = reverse("blog_categories")

        self.assertRegex(
            html,
            rf'<li[^>]*class="[^"]*\bexpanded\b[^"]*"[^>]*>\s*<a href="{re.escape(blog_href)}">Blog</a>',
        )
        self.assertRegex(
            html,
            rf'<li[^>]*class="[^"]*\bexpanded\b[^"]*"[^>]*>\s*<a href="{re.escape(cats_href)}">Categories</a>',
        )

        self.assertNotRegex(
            html,
            rf'<li[^>]*class="[^"]*\bactive\b[^"]*"[^>]*>\s*<a href="{re.escape(blog_href)}">Blog</a>',
        )
        self.assertNotRegex(
            html,
            rf'<li[^>]*class="[^"]*\bactive\b[^"]*"[^>]*>\s*<a href="{re.escape(cats_href)}">Categories</a>',
        )

    def test_unrelated_branches_not_expanded(self):
        """
        На '/blog/categories/1/' ветки, не лежащие в цепочке к активному,
        не должны получать 'expanded'.
        """
        html = self._render_template("/blog/categories/1/")

        # 'About' и 'External' — без классов
        self.assertInHTML(f'<li><a href="{reverse("about")}">About</a></li>', html)
        self.assertInHTML('<li><a href="http://example.com">External</a></li>', html)

        # И точно без expanded на этих ссылках
        self.assertNotRegex(html,
                            rf'<li[^>]*class="[^"]*\\bexpanded\\b[^"]*">\\s*<a href="{re.escape(reverse("about"))}">About</a>')
        self.assertNotRegex(html,
                            r'<li[^>]*class="[^"]*\bexpanded\b[^"]*">\s*<a href="http://example\.com">External</a>')

    def test_no_empty_class_attribute(self):
        """
        Никогда не должно быть пустого class="" или class=" ".
        """
        for path in [reverse("index"), reverse("blog"), reverse("blog_categories"), "/blog/categories/1/"]:
            html = self._render_template(path)
            self.assertNotIn('class=""', html)
            self.assertNotIn('class=" "', html)

    def test_no_active_item(self):
        """Если URL не совпадает ни с одним пунктом, классы не выставляются."""
        html = self._render_template("/some/non-menu/url/")

        self.assertNotIn("active", html)
        self.assertNotIn("expanded", html)

        # Убедимся, что пункты на месте
        self.assertIn("Home", html)
        self.assertIn("Blog", html)

    def test_other_menu_items_not_rendered(self):
        """Тег {% draw_menu 'main_menu' %} не должен рендерить пункты из 'footer_menu'."""
        html = self._render_template(reverse("index"))

        self.assertIn("Home", html)
        self.assertNotIn("Footer Link", html)