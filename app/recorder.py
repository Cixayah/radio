import os
import subprocess
import time

from .config import RECORD_DURATION
from .utils import br_timestamp, safe_filename


def recorder_worker(name, url, audio_path, work_queue, stop_event):
    print(f"  🎙️  Gravador iniciado: {name}")
    while not stop_event.is_set():
        ts = br_timestamp()
        file_path = os.path.join(audio_path, f"{safe_filename(name)}_{ts}.mp3")
        cmd = [
            "ffmpeg", "-i", url, "-t", str(RECORD_DURATION),
            "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
            file_path, "-y", "-loglevel", "quiet",
        ]
        try:
            subprocess.run(cmd, check=True, timeout=RECORD_DURATION + 15)
            if os.path.exists(file_path):
                work_queue.put((name, file_path))
        except Exception as e:
            print(f"  ⚠️  [{name}] Erro na gravação: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
        time.sleep(2)
    print(f"  🛑 Gravador encerrado: {name}")
