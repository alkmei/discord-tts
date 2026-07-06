from django.contrib import admin

from .models import AdminGuildPreferences
from .models import UserGuildPreferences


@admin.register(UserGuildPreferences)
class UserGuildPreferencesAdmin(admin.ModelAdmin):
    list_display = (
        "account__discord_id",
        "voice",
    )
    search_fields = ("account__discord_id",)


@admin.register(AdminGuildPreferences)
class AdminGuildPreferencesAdmin(admin.ModelAdmin):
    name = "Admin Guild Preferences"
    list_display = ("guild_id",)
    search_fields = ("guild_id",)
