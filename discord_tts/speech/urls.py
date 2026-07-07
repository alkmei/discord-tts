from django.urls import path

from . import views

app_name = "speech"

urlpatterns = [
    # The main dashboard interface
    path("", views.DashboardView.as_view(), name="dashboard"),
    # JSON endpoint for Monaco editor voice-highlighting
    path("voices/", views.voice_list, name="voice_list"),
    # HTMX endpoint for processing and dispatching TTS
    path("generate/", views.GenerateView.as_view(), name="generate"),
]
