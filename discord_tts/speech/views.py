from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from django.views.generic import View

from discord_tts.voices.interface import get_all_guild_voices

from .dispatcher import handle_multiline_tts


class DashboardView(TemplateView):
    template_name = "speech/index.html"


def voice_list(request):
    """Returns a JSON list of voice names for a specific guild."""
    guild_id_raw = request.GET.get("guild_id")
    try:
        guild_id = int(guild_id_raw) if guild_id_raw else 0
        voices = [v.name.lower() for v in get_all_guild_voices(guild_id)]
        return JsonResponse(list(voices), safe=False)
    except ValueError, TypeError:
        return JsonResponse([], safe=False)


class GenerateView(View):
    def post(self, request):
        text = request.POST.get("text", "").strip()
        guild_id_raw = request.POST.get("guild_id", "").strip()
        channel_id_raw = request.POST.get("channel_id", "").strip()

        if not text or not guild_id_raw or not channel_id_raw:
            return render(
                request,
                "speech/partials/error.html",
                {"message": "Missing text, Guild ID, or Channel ID."},
            )

        try:
            guild_id = int(guild_id_raw)
            channel_id = int(channel_id_raw)
            # Use the actual Discord ID of the logged-in user if available
            discord_id = getattr(request.user, "discord_id", 0)

            # 1. Pre-parse for UI feedback (to show warnings/line numbers)
            # We fetch voices here just to calculate the UI 'warnings'
            available_voices = [v.name.lower() for v in get_all_guild_voices(guild_id)]
            lines = text.splitlines()
            parsed_lines = []
            current_voice = available_voices[0] if available_voices else "default"

            for idx, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue

                warnings, voice_name, msg = [], current_voice, line
                if ":" in line:
                    pot_v, pot_t = line.split(":", 1)
                    pot_v = pot_v.strip().lower()
                    if pot_v in available_voices:
                        voice_name = pot_v
                        msg = pot_t.strip()
                        current_voice = voice_name
                    else:
                        warnings.append(
                            f"Voice '{pot_v}' not found - using '{current_voice}'",
                        )
                        msg = pot_t.strip()

                parsed_lines.append(
                    {
                        "line_num": idx,
                        "voice": voice_name,
                        "text": msg,
                        "warnings": warnings,
                    },
                )

            # 2. Call the Dispatcher (Actual Execution)
            # This handles Redis sequencing, cleaning, and Celery triggering
            queued_count = handle_multiline_tts(
                raw_text=text,
                guild_id=guild_id,
                discord_id=discord_id,
                channel_id=channel_id,
            )

            context = {
                "parsed_lines": parsed_lines,
                "guild_id": guild_id,
                "queued_count": queued_count,
            }
            return render(request, "speech/partials/result.html", context)

        except ValueError:
            return render(
                request,
                "speech/partials/error.html",
                {"message": "Invalid Guild ID or Channel ID."},
            )
