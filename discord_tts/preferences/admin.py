from django.contrib import admin

from .models import UserGuildPreferences


@admin.register(UserGuildPreferences)
class UserGuildPreferencesAdmin(admin.ModelAdmin):
    list_display = ("discord_id", "user", "voice", "introduce_speaker")
    search_fields = ("discord_id", "user__username")
