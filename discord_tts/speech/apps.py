import logging
import os
import sys

from django.apps import AppConfig
from huggingface_hub import login

logger = logging.getLogger(__name__)


class SpeechConfig(AppConfig):
    name = "discord_tts.speech"

    def ready(self):
        # We check if we are in a Celery worker or the Main process
        # This prevents the web-server from needing to login unnecessarily

        if "celery" in sys.argv or "worker" in sys.argv:
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                try:
                    login(token=hf_token)
                    logger.info(
                        "Successfully authenticated with HuggingFace.",
                    )
                except Exception as e:
                    logger.exception(f"Hugging Face login failed: {e}")
