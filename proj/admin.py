from django.contrib import admin

# Register your models here.

from .models import project,finance,favoriteProject


# class favoriteAdmin(admin.ModelAdmin):
#     def save_model(self, request, obj, form, change):
#         if change:
#             obj_old = self.model.objects.get(pk=obj.pk)
#         else:
#             obj_old = None
#
#         if obj_old:
#             favoritelist = favorite.objects.exclude(obj_old)

admin.site.register(project)
admin.site.register(finance)
admin.site.register(favoriteProject)
