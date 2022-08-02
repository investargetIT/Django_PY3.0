#!/usr/bin/env python
"""
WSGI config for invest project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os
import sys

import django

from django.core.wsgi import get_wsgi_application

from invest.settings import APILOG_PATH

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest.settings")

if 'uwsgi' in sys.argv:
    if os.path.exists(APILOG_PATH['qiniumarkFilePath']):
        os.remove(APILOG_PATH['qiniumarkFilePath'])
    if os.path.exists(APILOG_PATH['markFilePath']):
        os.remove(APILOG_PATH['markFilePath'])
application = get_wsgi_application()
