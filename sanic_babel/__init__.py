#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    sanic_babel
    ~~~~~~~~~~~~~~
    Inspired from flask-babel

    Implements i18n/l10n support for Flask applications based on Babel.

    :copyright: (c) 2013 by Armin Ronacher, Daniel Neuhäuser.
    :license: BSD, see LICENSE for more details.
"""
import os
from datetime import datetime
from contextlib import contextmanager
from itertools import repeat
from babel import dates, numbers, support, Locale
try:
    from pytz.gae import pytz
except ImportError:
    from pytz import timezone, UTC
else:
    timezone = pytz.timezone
    UTC = pytz.UTC

from sanic_babel.speaklater import LazyString


def is_immutable(self):
    raise TypeError('{!r} objects are immutable\
        '.format(self.__class__.__name__))


class ImmutableDictMixin:

    """Makes a :class:`dict` immutable.

    .. versionadded:: 0.5

    :private:
    """
    _hash_cache = None

    @classmethod
    def fromkeys(cls, keys, value=None):
        instance = super(cls, cls).__new__(cls)
        instance.__init__(zip(keys, repeat(value)))
        return instance

    def __reduce_ex__(self, protocol):
        return type(self), (dict(self),)

    def _iter_hashitems(self):
        return iter(self)

    def __hash__(self):
        if self._hash_cache is not None:
            return self._hash_cache

        rv = self._hash_cache = hash(frozenset(self._iter_hashitems()))
        return rv

    def setdefault(self, key, default=None):
        is_immutable(self)

    def update(self, *args, **kwargs):
        is_immutable(self)

    def pop(self, key, default=None):
        is_immutable(self)

    def popitem(self):
        is_immutable(self)

    def __setitem__(self, key, value):
        is_immutable(self)

    def __delitem__(self, key):
        is_immutable(self)

    def clear(self):
        is_immutable(self)


class ImmutableDict(ImmutableDictMixin, dict):

    """An immutable :class:`dict`.

    .. versionadded:: 0.5
    """

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__,
                               dict.__repr__(self),
                               )

    def copy(self):
        """Return a shallow mutable copy of this object.  Keep in mind that
        the standard library's :func:`copy` function is a no-op for this class
        like for any other python immutable type (eg: :class:`tuple`).
        """
        return dict(self)

    def __copy__(self):
        return self


class Babel:
    """Central controller class that can be used to configure how
    sanic-babel behaves.  Each application that wants to use sanic-babel
    has to create, or run :meth:`init_app` on, an instance of this class
    after the configuration was initialized.
    """

    default_date_formats = ImmutableDict({
        'time':             'medium',
        'date':             'medium',
        'datetime':         'medium',
        'time.short':       None,
        'time.medium':      None,
        'time.full':        None,
        'time.long':        None,
        'date.short':       None,
        'date.medium':      None,
        'date.full':        None,
        'date.long':        None,
        'datetime.short':   None,
        'datetime.medium':  None,
        'datetime.full':    None,
        'datetime.long':    None,
    })

    def __init__(self, app=None, default_locale='en', default_timezone='UTC',
                 date_formats=None, configure_jinja=True):
        self._default_locale = default_locale
        self._default_timezone = default_timezone
        self._date_formats = date_formats
        self._configure_jinja = configure_jinja
        self.app = app
        self.locale_selector_func = None
        self.timezone_selector_func = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Set up this instance for use with *app*, if no app was passed to
        the constructor.
        """
        self.app = app
        app.babel_instance = self
        if not hasattr(app, 'extensions'):
            app.extensions = {}

        app.extensions['babel'] = self
        app.babel_translations = {}  # cache translations per locale?

        app.config.setdefault('BABEL_DEFAULT_LOCALE', self._default_locale)
        app.config.setdefault('BABEL_DEFAULT_TIMEZONE', self._default_timezone)
        if self._date_formats is None:
            self._date_formats = self.default_date_formats.copy()

        #: a mapping of Babel datetime format strings that can be modified
        #: to change the defaults.  If you invoke :func:`format_datetime`
        #: and do not provide any format string sanic-babel will do the
        #: following things:
        #:
        #: 1.   look up ``date_formats['datetime']``.  By default ``'medium'``
        #:      is returned to enforce medium length datetime formats.
        #: 2.   ``date_formats['datetime.medium'] (if ``'medium'`` was
        #:      returned in step one) is looked up.  If the return value
        #:      is anything but `None` this is used as new format string.
        #:      otherwise the default for that language is used.
        self.date_formats = self._date_formats

        if self._configure_jinja:
            if not hasattr(app, 'jinja_env'):
                raise ValueError('app.jinja_env shoud be setup at first.')

            app.jinja_env.filters.update(
                datetimeformat=format_datetime,
                dateformat=format_date,
                timeformat=format_time,
                timedeltaformat=format_timedelta,

                numberformat=format_number,
                decimalformat=format_decimal,
                currencyformat=format_currency,
                percentformat=format_percent,
                scientificformat=format_scientific,
            )
            app.jinja_env.add_extension('jinja2.ext.i18n')
            app.jinja_env.newstyle_gettext = True
            # reference for update context in jinja_env
            self._get_translations = get_translations

    def localeselector(self, f):
        """Registers a callback function for locale selection.  The default
        behaves as if a function was registered that returns `None` all the
        time.  If `None` is returned, the locale falls back to the one from
        the configuration.

        This has to return the locale as string (eg: ``'de_AT'``, ''`en_US`'')
        """
        assert self.locale_selector_func is None, \
            'a localeselector function is already registered'
        self.locale_selector_func = f
        return f

    def timezoneselector(self, f):
        """Registers a callback function for timezone selection.  The default
        behaves as if a function was registered that returns `None` all the
        time.  If `None` is returned, the timezone falls back to the one from
        the configuration.

        This has to return the timezone as string (eg: ``'Europe/Vienna'``)
        """
        assert self.timezone_selector_func is None, \
            'a timezoneselector function is already registered'
        self.timezone_selector_func = f
        return f

    def list_translations(self):
        """Returns a list of all the locales translations exist for.  The
        list returned will be filled with actual locale objects and not just
        strings.
        """
        result = []

        for dirname in self.translation_directories:
            if not os.path.isdir(dirname):
                continue

            for folder in os.listdir(dirname):
                locale_dir = os.path.join(dirname, folder, 'LC_MESSAGES')
                if not os.path.isdir(locale_dir):
                    continue

                if filter(lambda x: x.endswith('.mo'), os.listdir(locale_dir)):
                    result.append(Locale.parse(folder))

        # If not other translations are found, add the default locale.
        if not result:
            result.append(Locale.parse(self._default_locale))

        return result

    @property
    def default_locale(self):
        """The default locale from the configuration as instance of a
        `babel.Locale` object.
        """
        return Locale.parse(self.app.config['BABEL_DEFAULT_LOCALE'])

    @property
    def default_timezone(self):
        """The default timezone from the configuration as instance of a
        `pytz.timezone` object.
        """
        return timezone(self.app.config['BABEL_DEFAULT_TIMEZONE'])

    @property
    def translation_directories(self):
        directories = self.app.config.get('BABEL_TRANSLATION_DIRECTORIES',
                                          'translations').split(';')

        root_path = getattr(self.app, 'root_path', None)
        for path in directories:
            if not os.path.isabs(path) and root_path is not None:
                path = os.path.join(root_path, path)

            yield path


def get_translations(request=None):
    """Returns the correct gettext translations that should be used for
    this request.  This will never fail and return a dummy translation
    object if used outside of the request or if a translation cannot be
    found.
    """
    if request is None:
        return support.NullTranslations()

    translations = request.get('babel_translations', None)
    if translations is None:
        app = request.app
        locale = get_locale(request)
        if locale in app.babel_translations:
            request['babel_translations'] = app.babel_translations[locale]
            return app.babel_translations[locale]

        translations = support.Translations()
        babel = app.babel_instance
        for dirname in babel.translation_directories:
            catalog = support.Translations.load(dirname, [locale])
            translations.merge(catalog)
            # FIXME: Workaround for merge() being really, really stupid. It
            # does not copy _info, plural(), or any other instance variables
            # populated by GNUTranslations. We probably want to stop using
            # `support.Translations.merge` entirely.
            if hasattr(catalog, 'plural'):
                translations.plural = catalog.plural

        request['babel_translations'] = translations
        app.babel_translations[locale] = translations

    return translations


def get_locale(request=None):
    """Returns the locale that should be used for this request as
    `babel.Locale` object.  This returns `Locale.parse('en')` if used outside
    of a request.
    """
    if request is None:
        return Locale.parse('en')

    locale = request.get('babel_locale', None)
    if locale is None:
        babel = request.app.babel_instance
        if babel.locale_selector_func is None:
            locale = babel.default_locale
        else:
            rv = babel.locale_selector_func(request)
            if rv is None:
                locale = babel.default_locale
            else:
                locale = Locale.parse(rv)

        request['babel_locale'] = locale

    return locale


def get_timezone(request=None):
    """Returns the timezone that should be used for this request as
    `pytz.timezone` object.  This returns `UTC` if used outside of
    a request.
    """
    if request is None:
        return UTC

    tzinfo = request.get('babel_tzinfo')
    if tzinfo is None:
        babel = request.app.babel_instance
        if babel.timezone_selector_func is None:
            tzinfo = babel.default_timezone
        else:
            rv = babel.timezone_selector_func(request)
            if rv is None:
                tzinfo = babel.default_timezone
            else:
                if isinstance(rv, str):
                    tzinfo = timezone(rv)
                else:
                    tzinfo = rv

        request['babel_tzinfo'] = tzinfo

    return tzinfo


def refresh(request):
    """Refreshes the cached timezones and locale information.  This can
    be used to switch a translation between a request and if you want
    the changes to take place immediately, not just with the next request::

        user.timezone = request.form['timezone']
        user.locale = request.form['locale']
        refresh(request)
        jinja.flash(gettext('Language was changed', request))

    NOTICE: :func:`jinja.flash` function is from `sanic-jinja2` package.

    Without that refresh, the :func:`jinja.flash` function would probably
    return English text and a now German page.
    """
    for key in 'babel_locale', 'babel_tzinfo', 'babel_translations':
        if key in request:
            request.pop(key)


@contextmanager
def force_locale(locale, request=None):
    """Temporarily overrides the currently selected locale.

    Sometimes it is useful to switch the current locale to different one, do
    some tasks and then revert back to the original one. For example, if the
    user uses German on the web site, but you want to send them an email in
    English, you can use this function as a context manager::

        with force_locale('en_US', request):
            send_email(gettext('Hello!', request), ...)

    :param locale: The locale to temporary switch to (ex: 'en_US').
    :param request: the current Request object
    """
    if request is None:
        yield
        return

    babel = request.app.babel_instance

    orig_locale_selector_func = babel.locale_selector_func
    orig_attrs = {}
    for key in ('babel_translations', 'babel_locale'):
        orig_attrs[key] = request.get(key, None)

    try:
        babel.locale_selector_func = lambda request: locale
        for key in orig_attrs:
            request[key] = None
        yield
    finally:
        babel.locale_selector_func = orig_locale_selector_func
        for key, value in orig_attrs.items():
            request[key] = value


def _get_format(key, format, request):
    """A small helper for the datetime formatting functions.  Looks up
    format defaults for different kinds.
    """
    if request is None:
        formats = Babel.default_date_formats.copy()
    else:
        formats = request.app.extensions['babel'].date_formats

    if format is None:
        format = formats[key]

    if format in ('short', 'medium', 'full', 'long'):
        rv = formats['{}.{}'.format(key, format)]
        if rv is not None:
            format = rv

    return format


def to_user_timezone(datetime, request=None):
    """Convert a datetime object to the user's timezone.  This automatically
    happens on all date formatting unless rebasing is disabled.  If you need
    to convert a :class:`datetime.datetime` object at any time to the user's
    timezone (as returned by :func:`get_timezone` this function can be used).
    """
    if datetime.tzinfo is None:
        datetime = datetime.replace(tzinfo=UTC)

    tzinfo = get_timezone(request)
    return tzinfo.normalize(datetime.astimezone(tzinfo))


def to_utc(datetime, request=None):
    """Convert a datetime object to UTC and drop tzinfo.  This is the
    opposite operation to :func:`to_user_timezone`.
    """
    if datetime.tzinfo is None:
        datetime = get_timezone(request).localize(datetime)

    return datetime.astimezone(UTC).replace(tzinfo=None)


def format_datetime(datetime=None, format=None, rebase=True, request=None):
    """Return a date formatted according to the given pattern.  If no
    :class:`~datetime.datetime` object is passed, the current time is
    assumed.  By default rebasing happens which causes the object to
    be converted to the users's timezone (as returned by
    :func:`to_user_timezone`).  This function formats both date and
    time.

    The format parameter can either be ``'short'``, ``'medium'``,
    ``'long'`` or ``'full'`` (in which cause the language's default for
    that setting is used, or the default from the :attr:`Babel.date_formats`
    mapping is used) or a format string as documented by Babel.

    This function is also available in the template context as filter
    named `datetimeformat`.
    """
    format = _get_format('datetime', format, request)
    return _date_format(dates.format_datetime, datetime, format, rebase,
                        request=request)


def format_date(date=None, format=None, rebase=True, request=None):
    """Return a date formatted according to the given pattern.  If no
    :class:`~datetime.datetime` or :class:`~datetime.date` object is passed,
    the current time is assumed.  By default rebasing happens which causes
    the object to be converted to the users's timezone (as returned by
    :func:`to_user_timezone`).  This function only formats the date part
    of a :class:`~datetime.datetime` object.

    The format parameter can either be ``'short'``, ``'medium'``,
    ``'long'`` or ``'full'`` (in which cause the language's default for
    that setting is used, or the default from the :attr:`Babel.date_formats`
    mapping is used) or a format string as documented by Babel.

    This function is also available in the template context as filter
    named `dateformat`.
    """
    if rebase and isinstance(date, datetime):
        date = to_user_timezone(date)

    format = _get_format('date', format, request)
    return _date_format(dates.format_date, date, format, rebase,
                        request=request)


def format_time(time=None, format=None, rebase=True, request=None):
    """Return a time formatted according to the given pattern.  If no
    :class:`~datetime.datetime` object is passed, the current time is
    assumed.  By default rebasing happens which causes the object to
    be converted to the users's timezone (as returned by
    :func:`to_user_timezone`).  This function formats both date and
    time.

    The format parameter can either be ``'short'``, ``'medium'``,
    ``'long'`` or ``'full'`` (in which cause the language's default for
    that setting is used, or the default from the :attr:`Babel.date_formats`
    mapping is used) or a format string as documented by Babel.

    This function is also available in the template context as filter
    named `timeformat`.
    """
    format = _get_format('time', format, request)
    return _date_format(dates.format_time, time, format, rebase,
                        request=request)


def format_timedelta(datetime_or_timedelta, granularity='second',
                     add_direction=False, threshold=0.85, request=None):
    """Format the elapsed time from the given date to now or the given
    timedelta.

    This function is also available in the template context as filter
    named `timedeltaformat`.
    """
    if isinstance(datetime_or_timedelta, datetime):
        datetime_or_timedelta = datetime.utcnow() - datetime_or_timedelta

    return dates.format_timedelta(
        datetime_or_timedelta,
        granularity,
        threshold=threshold,
        add_direction=add_direction,
        locale=get_locale(request)
    )


def _date_format(formatter, obj, format, rebase, request=None, **extra):
    """Internal helper that formats the date."""
    locale = get_locale(request)
    extra = {}
    if formatter is not dates.format_date and rebase:
        extra['tzinfo'] = get_timezone(request)
    return formatter(obj, format, locale=locale, **extra)


def format_number(number, request=None):
    """Return the given number formatted for the locale in request

    :param number: the number to format
    :param request: the current Request object
    :return: the formatted number
    :rtype: str
    """
    locale = get_locale(request)
    return numbers.format_number(number, locale=locale)


def format_decimal(number, format=None, request=None):
    """Return the given decimal number formatted for the locale in request

    :param number: the number to format
    :param format: the format to use
    :param request: the current Request object
    :return: the formatted number
    :rtype: str
    """
    locale = get_locale(request)
    return numbers.format_decimal(number, format=format, locale=locale)


def format_currency(number, currency, format=None, currency_digits=True,
                    format_type='standard', request=None):
    """Return the given number formatted for the locale in request

    :param number: the number to format
    :param currency: the currency code
    :param format: the format to use
    :param currency_digits: use the currency’s number of decimal digits
                            [default: True]
    :param format_type: the currency format type to use
                        [default: standard]
    :param request: the current Request object
    :return: the formatted number
    :rtype: str
    """
    locale = get_locale(request)
    return numbers.format_currency(
        number,
        currency,
        format=format,
        locale=locale,
        currency_digits=currency_digits,
        format_type=format_type
    )


def format_percent(number, format=None, request=None):
    """Return formatted percent value for the locale in request

    :param number: the number to format
    :param format: the format to use
    :param request: the current Request object
    :return: the formatted percent number
    :rtype: str
    """
    locale = get_locale(request)
    return numbers.format_percent(number, format=format, locale=locale)


def format_scientific(number, format=None, request=None):
    """Return value formatted in scientific notation for the locale in request

    :param number: the number to format
    :param format: the format to use
    :param request: the current Request object
    :return: the formatted percent number
    :rtype: str
    """
    locale = get_locale(request)
    return numbers.format_scientific(number, format=format, locale=locale)


def gettext(string, request=None, **variables):
    """Translates a string with the current locale and passes in the
    given keyword arguments as mapping to a string formatting string.

    ::

        gettext('Hello World!', request)
        gettext('Hello %(name)s!', request, name='World')
    """
    t = get_translations(request)
    if t is None:
        return (string % variables) if variables else string

    s = t.ugettext(string)
    return (s % variables) if variables else s


_ = gettext


def ngettext(singular, plural, num, request=None, **variables):
    """Translates a string with the current locale and passes in the
    given keyword arguments as mapping to a string formatting string.
    The `num` parameter is used to dispatch between singular and various
    plural forms of the message.  It is available in the format string
    as ``%(num)d`` or ``%(num)s``.  The source language should be
    English or a similar language which only has one plural form.

    ::

        ngettext('%(num)d Apple', '%(num)d Apples', request=request,
                 num=len(apples))
    """
    variables.setdefault('num', num)
    t = get_translations(request)
    if t is None:
        s = singular if num == 1 else plural
        return s if not variables else s % variables

    s = t.ungettext(singular, plural, num)
    return s if not variables else s % variables


def pgettext(context, string, request=None, **variables):
    """Like :func:`gettext` but with a context.
    """
    t = get_translations(request)
    if t is None:
        return string if not variables else string % variables

    s = t.upgettext(context, string)
    return s if not variables else s % variables


def npgettext(context, singular, plural, num, request=None, **variables):
    """Like :func:`ngettext` but with a context.
    """
    variables.setdefault('num', num)
    t = get_translations(request)
    if t is None:
        s = singular if num == 1 else plural
        return s if not variables else s % variables

    s = t.unpgettext(context, singular, plural, num)
    return s if not variables else s % variables


def lazy_gettext(string, **variables):
    """Like :func:`gettext` but the string returned is lazy which means
    it will be translated when it is used as an actual string.

    NOTE: As `sanic` does not provide something like `ctx_stack`, the
    `lazy object` should call with `request` before using as an actual string.

    Example::

        hello = lazy_gettext('Hello World')

        @app.route('/')
        def index(request):
            return str(hello(request))
    """
    return LazyString(gettext, string, **variables)


def lazy_pgettext(context, string, **variables):
    """Like :func:`pgettext` but the string returned is lazy which means
    it will be translated when it is used as an actual string.
    """
    return LazyString(pgettext, context, string, **variables)
