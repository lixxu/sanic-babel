"""
sanic-babel
-----------

Adds i18n/l10n support to Sanic applications with the help of the
`Babel`_ library.

Links
`````

* `documentation <http://pythonhosted.org/sanic-babel/>`_

.. _Babel: http://babel.edgewall.org/

"""
from setuptools import setup

setup(
    name='sanic-babel',
    version='0.1.1',
    url='https://github.com/lixxu/sanic-babel',
    license='BSD',
    author='Lix Xu',
    author_email='xuzenglin@gmail.com',
    description='babel support for sanic',
    long_description=__doc__,
    packages=['sanic_babel'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'Sanic>=0.4.1',
        'Babel>=2.3',
        'Jinja2>=2.5',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ]
)
