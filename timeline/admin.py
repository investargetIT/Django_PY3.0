from django.contrib import admin

# Register your models here.
from timeline.models import timelineTransationStatu, timeline

admin.site.register(timeline)
admin.site.register(timelineTransationStatu)