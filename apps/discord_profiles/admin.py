from django.contrib import admin

from .models import DiscordUserProfile


@admin.register(DiscordUserProfile)
class DiscordUserProfileAdmin(admin.ModelAdmin):
    list_display = ("discord_id", "user", "voice", "introduce_speaker")
    search_fields = ("discord_id", "user__username")
