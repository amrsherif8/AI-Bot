
import threading
import pygame
import os

pygame.mixer.init()
AUDIO_FILE = "Sound.mp3"

# Prevent the app from crashing if the file is missing
if os.path.exists(AUDIO_FILE):
    pygame.mixer.music.load(AUDIO_FILE)
else:
    print(f"Warning: Audio file '{AUDIO_FILE}' not found in the working directory.")

WORDS = {
    "hi": (12, 15),
    "Hamza": (0, 4),
    "Ahmed": (4, 8),
}

stop_timer = None

def list_sounds():
    """Returns a list of available sounds and their durations for the API."""
    return [{"word": word, "duration": end - start} for word, (start, end) in WORDS.items()]

def find_sound(word):
    return WORDS.get(word)

def play_word(word):
    global stop_timer
    start, end = WORDS[word]
    if stop_timer:
        stop_timer.cancel()
    
    # Check if music is actually loaded before playing
    if os.path.exists(AUDIO_FILE):
        pygame.mixer.music.play(start=start)
        stop_timer = threading.Timer(end - start, pygame.mixer.music.stop)
        stop_timer.start()
    else:
        print(f"Cannot play '{word}', audio file is missing.")

def trigger_sound(text):
    text = text.lower()
    for word in WORDS:
        if word.lower() in text and find_sound(word):
            play_word(word)
            return True
    return False





# import threading

# import pygame

# pygame.mixer.init()
# AUDIO_FILE = "Sound_1.mp3"
# pygame.mixer.music.load(AUDIO_FILE)


# WORDS = {
#     "hi": (12, 15),
#     "Hamza": (0, 4),
#     "Ahmed": (4, 8),
# }

# stop_timer = None


# def find_sound(word):
#     return WORDS.get(word)


# def play_word(word):
#     global stop_timer
#     start, end = WORDS[word]
#     if stop_timer:
#         stop_timer.cancel()
#     pygame.mixer.music.play(start=start)
#     stop_timer = threading.Timer(end - start, pygame.mixer.music.stop)
#     stop_timer.start()


# def trigger_sound(text):
#     text = text.lower()
#     for word in WORDS:
#         if word in text and find_sound(word):
#             play_word(word)
#             return True
#     return False


#solf



