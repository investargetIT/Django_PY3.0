#!/usr/bin/env python
import os
import sys

from invest.settings import APILOG_PATH

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
            django.setup()
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    if 'runserver' in sys.argv:
        if os.path.exists(APILOG_PATH['qiniumarkFilePath']):
            os.remove(APILOG_PATH['qiniumarkFilePath'])
        if os.path.exists(APILOG_PATH['markFilePath']):
            os.remove(APILOG_PATH['markFilePath'])
    execute_from_command_line(sys.argv)
