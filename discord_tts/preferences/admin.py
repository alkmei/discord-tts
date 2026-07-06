from django.contrib import admin

from .models import UserGuildPreferences


@admin.register(UserGuildPreferences)
class UserGuildPreferencesAdmin(admin.ModelAdmin):
    list_display = (
        "account__discord_id",
        "voice",
    )
    search_fields = ("account__discord_id",)


class AdminGuildPreferencesAdmin(admin.ModelAdmin):
    list_display = ("guild_id",)
    search_fields = ("guild_id",)
