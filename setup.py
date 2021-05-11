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
import os
import platform
from pathlib import Path

from setuptools import setup

if platform.system().startswith("Windows"):
    os.environ["SANIC_NO_UVLOOP"] = "yes"

version = ""
p = Path(__file__) / "../sanic_babel/__init__.py"
with p.resolve().open(encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__ = "):
            version = line.split("=")[-1].strip().replace("'", "")
            break

setup(
    name="sanic-babel",
    version=version.replace('"', ""),
    url="https://github.com/lixxu/sanic-babel",
    license="BSD",
    author="Lix Xu",
    author_email="xuzenglin@gmail.com",
    description="babel support for sanic",
    long_description=__doc__,
    packages=["sanic_babel"],
    zip_safe=False,
    platforms="any",
    install_requires=["Sanic>=21.3", "Babel>=2.3", "Jinja2>=2.5"],
    python_requires=">=3.7",
    classifiers=[
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
    ],
)
