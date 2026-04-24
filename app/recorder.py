import os
import subprocess
import sys
import time

from .config import RECORD_DURATION
from .utils import br_timestamp, safe_filename


def recorder_worker(name, url, audio_path, work_queue, stop_event, pause_event=None):
    print(f"  🎙️  Gravador iniciado: {name}")

    startupinfo = None
    creationflags = 0
    if sys.platform.startswith("win"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW

    was_paused = False
    while not stop_event.is_set():
        if pause_event is not None and pause_event.is_set():
            if not was_paused:
                print(f"  ⏸️  [{name}] Pausado")
                was_paused = True
            time.sleep(1)
            continue

        if was_paused:
            print(f"  ▶️  [{name}] Retomado")
            was_paused = False

        ts = br_timestamp()
        file_path = os.path.join(audio_path, f"{safe_filename(name)}_{ts}.mp3")
        cmd = [
            "ffmpeg", "-i", url, "-t", str(RECORD_DURATION),
            "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
            file_path, "-y", "-loglevel", "quiet",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            while proc.poll() is None:
                if stop_event.is_set():
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    break
                time.sleep(0.25)

            if proc.returncode == 0 and os.path.exists(file_path):
                work_queue.put((name, file_path))
            elif os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"  ⚠️  [{name}] Erro na gravação: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
        time.sleep(2)
    print(f"  🛑 Gravador encerrado: {name}")
