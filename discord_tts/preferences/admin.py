from django.contrib import admin

from .models import AdminGuildPreferences
from .models import UserGuildPreferences


@admin.register(UserGuildPreferences)
class UserGuildPreferencesAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "guild_id",
        "voice",
    )
    list_filter = ("guild_id",)
    search_fields = (
        "account__discord_id",
        "guild_id",
    )


@admin.register(AdminGuildPreferences)
class AdminGuildPreferencesAdmin(admin.ModelAdmin):
    name = "Admin Guild Preferences"
    list_display = ("guild_id",)
    search_fields = ("guild_id",)
