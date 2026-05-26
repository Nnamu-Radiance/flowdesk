from django.contrib import admin

from apps.notifications.models import Notification, Subscription

admin.site.register(Notification)
admin.site.register(Subscription)
