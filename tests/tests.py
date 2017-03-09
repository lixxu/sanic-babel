#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pickle

import unittest
from decimal import Decimal
import sanic
from sanic.response import text
from datetime import datetime, timedelta
import sanic_babel as babel
from sanic_babel import gettext, ngettext, lazy_gettext, get_translations
from babel.support import NullTranslations
from sanic_jinja2 import SanicJinja2


def get_app():
    app = sanic.Sanic(__name__)

    @app.route('/')
    async def hello(request):
        return text('hello')

    return app


def get_babel(app=None, **kwargs):
    return babel.Babel(app=app, configure_jinja=False, **kwargs)


class IntegrationTestCase(unittest.TestCase):
    def test_no_request_context(self):
        app = get_app()

        b = get_babel()
        b.init_app(app)

        assert isinstance(get_translations(), NullTranslations)

    def test_multiple_directories(self):
        """
        Ensure we can load translations from multiple directories.
        """
        app = get_app()
        b = get_babel()

        app.config.update({
            'BABEL_TRANSLATION_DIRECTORIES': ';'.join((
                'translations',
                'renamed_translations'
            )),
            'BABEL_DEFAULT_LOCALE': 'de_DE'
        })

        b.init_app(app)

        request, response = app.test_client.get('/')
        translations = b.list_translations()

        assert(len(translations) == 2)
        assert(str(translations[0]) == 'de')
        assert(str(translations[1]) == 'de')

        assert gettext('Hello %(name)s!', name='Peter',
                       request=request) == 'Hallo Peter!'

    def test_lazy_old_style_formatting(self):
        app = get_app()
        get_babel(app)

        lazy_string = lazy_gettext('Hello %(name)s')
        request, response = app.test_client.get('/')
        assert lazy_string(request) % {'name': 'test'} == 'Hello test'

        lazy_string = lazy_gettext('test')
        assert 'Hello %s' % lazy_string(request) == 'Hello test'

    def test_lazy_pickling(self):
        app = get_app()
        get_babel(app)
        request, response = app.test_client.get('/')

        lazy_string = lazy_gettext('Foo')
        pickled = pickle.dumps(lazy_string)
        unpickled = pickle.loads(pickled)

        assert unpickled == lazy_string


class DateFormattingTestCase(unittest.TestCase):

    def test_basics(self):
        app = get_app()
        get_babel(app)

        request, response = app.test_client.get('/')

        d = datetime(2010, 4, 12, 13, 46)
        delta = timedelta(days=6)

        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 1:46:00 PM'
        assert babel.format_date(d, request=request) == 'Apr 12, 2010'
        assert babel.format_time(d, request=request) == '1:46:00 PM'
        assert babel.format_timedelta(delta, request=request) == '1 week'
        assert babel.format_timedelta(delta, threshold=1, request=request) == \
            '6 days'

        app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Vienna'
        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 3:46:00 PM'
        assert babel.format_date(d, request=request) == 'Apr 12, 2010'
        assert babel.format_time(d, request=request) == '3:46:00 PM'

        app.config['BABEL_DEFAULT_LOCALE'] = 'de_DE'
        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, 'long', request=request) == \
            '12. April 2010 um 15:46:00 MESZ'

    def test_init_app(self):
        b = get_babel()
        app = get_app()
        b.init_app(app)
        d = datetime(2010, 4, 12, 13, 46)

        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 1:46:00 PM'
        assert babel.format_date(d, request=request) == 'Apr 12, 2010'
        assert babel.format_time(d, request=request) == '1:46:00 PM'

        app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Vienna'
        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 3:46:00 PM'
        assert babel.format_date(d, request=request) == 'Apr 12, 2010'
        assert babel.format_time(d, request=request) == '3:46:00 PM'

        app.config['BABEL_DEFAULT_LOCALE'] = 'de_DE'
        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, 'long', request=request) == \
            '12. April 2010 um 15:46:00 MESZ'

    def test_custom_formats(self):
        app = get_app()
        app.config.update(
            BABEL_DEFAULT_LOCALE='en_US',
            BABEL_DEFAULT_TIMEZONE='Pacific/Johnston'
        )
        b = get_babel(app)
        b.date_formats['datetime'] = 'long'
        b.date_formats['datetime.long'] = 'MMMM d, yyyy h:mm:ss a'
        d = datetime(2010, 4, 12, 13, 46)

        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, request=request) == \
            'April 12, 2010 3:46:00 AM'

    def test_custom_locale_selector(self):
        app = get_app()
        b = get_babel(app)

        d = datetime(2010, 4, 12, 13, 46)

        the_timezone = 'UTC'
        the_locale = 'en_US'

        @b.localeselector
        def select_locale(request):
            return the_locale

        @b.timezoneselector
        def select_timezone(request):
            return the_timezone

        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 1:46:00 PM'

        the_locale = 'de_DE'
        the_timezone = 'Europe/Vienna'

        request, response = app.test_client.get('/')
        assert babel.format_datetime(d, request=request) == \
            '12.04.2010, 15:46:00'

    def test_refreshing(self):
        app = get_app()
        get_babel(app)
        request, response = app.test_client.get('/')

        d = datetime(2010, 4, 12, 13, 46)
        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 1:46:00 PM'
        app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Vienna'
        babel.refresh(request)
        assert babel.format_datetime(d, request=request) == \
            'Apr 12, 2010, 3:46:00 PM'

    def test_force_locale(self):
        app = get_app()
        b = get_babel(app)

        @b.localeselector
        def select_locale(request):
            return 'de_DE'

        request, response = app.test_client.get('/')
        assert str(babel.get_locale(request)) == 'de_DE'

        with babel.force_locale('en_US', request):
            assert str(babel.get_locale(request)) == 'en_US'

        assert str(babel.get_locale(request)) == 'de_DE'


class NumberFormattingTestCase(unittest.TestCase):

    def test_basics(self):
        app = get_app()
        get_babel(app)
        n = 1099

        request, response = app.test_client.get('/')
        assert babel.format_number(n, request=request) == '1,099'
        assert babel.format_decimal(Decimal('1010.99'), request=request) == \
            '1,010.99'
        assert babel.format_currency(n, 'USD', request=request) == '$1,099.00'
        assert babel.format_percent(0.19, request=request) == '19%'
        assert babel.format_scientific(10000, request=request) == '1E4'


class GettextTestCase(unittest.TestCase):

    def test_basics(self):
        app = get_app()
        get_babel(app, default_locale='de_DE')

        request, response = app.test_client.get('/')
        assert gettext('Hello %(name)s!', name='Peter', request=request) == \
            'Hallo Peter!'
        assert ngettext('%(num)s Apple', '%(num)s Apples', 3,
                        request=request) == '3 Äpfel'
        assert ngettext('%(num)s Apple', '%(num)s Apples', 1,
                        request=request) == '1 Apfel'

    def test_template_basics(self):
        app = get_app()
        jinja = SanicJinja2(app, autoescape=True)
        babel.Babel(app, default_locale='de_DE')

        t = lambda x, request: jinja.render_source('{{ %s }}' % x, request)

        request, response = app.test_client.get('/')
        assert t("gettext('Hello %(name)s!', name='Peter')", request) == \
            'Hallo Peter!'
        assert t("ngettext('%(num)s Apple', '%(num)s Apples', 3)",
                 request) == '3 Äpfel'
        assert t("ngettext('%(num)s Apple', '%(num)s Apples', 1)",
                 request) == '1 Apfel'
        assert jinja.render_source('''
            {% trans %}Hello {{ name }}!{% endtrans %}
        ''', request, name='Peter').strip() == 'Hallo Peter!'
        assert jinja.render_source('''
            {% trans num=3 %}{{ num }} Apple
            {%- pluralize %}{{ num }} Apples{% endtrans %}
        ''', request, name='Peter').strip() == '3 Äpfel'

    def test_lazy_gettext(self):
        app = get_app()
        get_babel(app, default_locale='de_DE')
        yes = lazy_gettext('Yes')

        request, response = app.test_client.get('/')
        yes(request)
        assert str(yes) == 'Ja'
        assert yes.__html__() == 'Ja'

        app.config['BABEL_DEFAULT_LOCALE'] = 'en_US'
        request, response = app.test_client.get('/')
        yes(request)
        assert str(yes) == 'Yes'
        assert yes.__html__() == 'Yes'

    def test_list_translations(self):
        app = get_app()
        b = get_babel(app, default_locale='de_DE')
        translations = b.list_translations()
        assert len(translations) == 1
        assert str(translations[0]) == 'de'

    def test_no_formatting(self):
        """
        Ensure we don't format strings unless a variable is passed.
        """
        app = get_app()
        get_babel(app)

        request, response = app.test_client.get('/')
        assert gettext('Test %s', request=request) == 'Test %s'
        assert gettext('Test %(name)s', name='test', request=request) == \
            'Test test'
        assert gettext('Test %s', request=request) % 'test' == 'Test test'


if __name__ == '__main__':
    unittest.main()
