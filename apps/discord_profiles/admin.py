from django.contrib import admin

from .models import UserPreferences


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ("discord_id", "user", "voice", "introduce_speaker")
    search_fields = ("discord_id", "user__username")
