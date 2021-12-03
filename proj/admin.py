from django.contrib import admin

# Register your models here.

from .models import project,finance



admin.site.register(project)
admin.site.register(finance)
