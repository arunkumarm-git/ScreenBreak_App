# assets.py
import os
import sys
import random
from PyQt6.QtCore import QStandardPaths

def _get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(_get_base_path(), "assets")

USER_DATA_DIR = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
USER_GIFS_DIR = os.path.join(USER_DATA_DIR, "gifs")
USER_SOUNDS_DIR = os.path.join(USER_DATA_DIR, "sounds")

os.makedirs(USER_GIFS_DIR, exist_ok=True)
os.makedirs(USER_SOUNDS_DIR, exist_ok=True)

class LocalAssetPicker:
    def __init__(self):
        self._gif_path:   str | None = None
        self._sound_path: str | None = None

    def start(self, is_pro: bool = False):
        self._gif_path   = self._pick_random_gif(is_pro)
        self._sound_path = self._pick_random_sound(is_pro)
        print(f"[assets] GIF  : {self._gif_path or 'none'}")
        print(f"[assets] Sound: {self._sound_path or 'none'}")

    def pop(self) -> tuple[str | None, str | None]:
        gif, sound = self._gif_path, self._sound_path
        self._gif_path = self._sound_path = None
        return gif, sound

    def _pick_random_gif(self, is_pro: bool = False) -> str | None:
        candidate_roots = [os.path.join(ASSETS_DIR, "gifs")]
        if is_pro and os.path.isdir(USER_GIFS_DIR):
            candidate_roots.append(USER_GIFS_DIR)

        all_gifs = []
        for root in candidate_roots:
            for dirpath, _, files in os.walk(root):
                all_gifs += [os.path.join(dirpath, f) for f in files if f.lower().endswith(".gif")]
        return random.choice(all_gifs) if all_gifs else None

    def _pick_random_sound(self, is_pro: bool = False) -> str | None:
        roots = [os.path.join(ASSETS_DIR, "sounds")]
        if is_pro and os.path.isdir(USER_SOUNDS_DIR):
            roots.append(USER_SOUNDS_DIR)
            
        sounds = []
        for root in roots:
            if os.path.isdir(root):
                sounds += [os.path.join(root, f) for f in os.listdir(root) if f.lower().endswith((".mp3", ".wav", ".ogg"))]
        return random.choice(sounds) if sounds else None