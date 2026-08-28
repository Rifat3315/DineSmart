# Use PyMySQL as a drop-in replacement for mysqlclient.
# This avoids needing a C compiler / Visual Studio Build Tools on Windows —
# `pip install pymysql` is pure Python and always works.
import pymysql

pymysql.install_as_MySQLdb()

# Django's MySQL backend checks the driver's reported version and expects
# it to look like mysqlclient's versioning (>= 2.2.1). PyMySQL reports its
# own version instead, which fails that check — so we spoof it here.
pymysql.version_info = (2, 2, 4, "final", 0)
pymysql.__version__ = "2.2.4"

# ---------------------------------------------------------------
# Compatibility patch: Django 4.2 (needed for MariaDB 10.4 support
# in XAMPP) uses an old internal trick to copy template Context
# objects that breaks on Python 3.14. Later Django versions fixed
# this the same way below — we apply that same fix here so we can
# keep Django 4.2 + Python 3.14 + MariaDB 10.4 all working together.
# Safe to remove once XAMPP's MariaDB is upgraded to 10.5+ and
# Django is upgraded alongside it.
# ---------------------------------------------------------------
import sys

if sys.version_info >= (3, 13):
    from copy import copy as _copy

    import django.template.context as _dj_context

    def _fixed_copy(self):
        duplicate = _dj_context.BaseContext()
        duplicate.__class__ = self.__class__
        duplicate.__dict__ = _copy(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    _dj_context.BaseContext.__copy__ = _fixed_copy

