from django.contrib import admin

from apps.auth.models import CustomUser

admin.site.register(CustomUser)
