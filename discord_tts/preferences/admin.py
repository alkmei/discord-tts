from django.contrib import admin

from .models import UserGuildPreferences


@admin.register(UserGuildPreferences)
class UserGuildPreferencesAdmin(admin.ModelAdmin):
    list_display = (
        "account__discord_id",
        "voice",
    )
    search_fields = ("account__discord_id",)
