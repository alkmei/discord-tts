import threading

from pocket_tts import TTSModel

# Use a threading lock just in case the worker is run with threads
_model_lock = threading.Lock()
tts_model = None


def get_model():
    global tts_model
    with _model_lock:
        if tts_model is None:
            tts_model = TTSModel.load_model()
    return tts_model
