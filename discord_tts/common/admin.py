from django.contrib import admin

from .models import DiscordAccount


@admin.register(DiscordAccount)
class DiscordAccountAdmin(admin.ModelAdmin):
    list_display = ("discord_id",)
    search_fields = ("discord_id",)
