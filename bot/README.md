# architecture

The bot works by having sending tasks to Celery to generate sound files.

Celery sends a signal to redis for the bot to pick up and play.
