## Commands

- `/join` - Join the voice channel you are in and bind to the current text channel
- `/leave` - Leave the current voice channel
- `/say` - Make the bot speak text (optional: specify a voice)
- `/multi` - Open a modal to play multiple voicelines with different voices
- `/stop` - Stop current playback and clear the queue for the channel
- `/skip` - Skip the current or next message in the queue
- `/settings` - Adjust your personal preferences (voice, introduce_speaker)

## Architecture

The bot interfaces with Django by setting it up with `django.setup()` in `main.py`.
It uses Celery for workers, which is configured in Django.

## TODO

- [ ] Admins should be able to configure the behavior they want the users to be able to control
- [ ] Testing
- [ ] Make it so some voices can be limited to certain users
- [x] Seperate voice settings into it's own command, and have a modal manage the rest of the preferences
- [x] lines do NOT play in order!
- [x] stop and skip do the same thing (also don't work)