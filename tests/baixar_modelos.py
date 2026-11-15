"""Baixa o modelo de separação de 6 stems para modelos/separacao (usado na compilação)."""
from audio_separator.separator import Separator
Separator.check_ffmpeg_installed = lambda self: None
s = Separator(model_file_dir="modelos/separacao")
s.download_model_files("htdemucs_6s.yaml")
