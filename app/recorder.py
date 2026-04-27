import os
import shutil
import subprocess
import sys
import time

from .config import RECORD_DURATION
from .utils import br_timestamp, safe_filename


def _resolve_ffmpeg_cmd() -> str | None:
    """Resolve ffmpeg executable from env, PATH, or bundled app locations.
    
    Search order:
    1. FFMPEG_PATH environment variable
    2. System PATH (via shutil.which)
    3. _MEIPASS/_internal (PyInstaller extracted data)
    4. Executable directory (bin/ subfolder or root)
    5. Project root bin/ (development)
    """
    exe_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    candidates = []
    debug_info = []

    # 1. Check FFMPEG_PATH environment variable
    env_path = os.getenv("FFMPEG_PATH")
    if env_path:
        if os.path.isfile(env_path):
            debug_info.append(f"✓ Found via FFMPEG_PATH: {env_path}")
            for msg in debug_info:
                if msg.startswith("✓"):
                    print(f"  {msg}")
            return env_path
        else:
            debug_info.append(f"✗ FFMPEG_PATH set but file not found: {env_path}")

    # 2. Check system PATH
    in_path = shutil.which("ffmpeg")
    if in_path:
        debug_info.append(f"✓ Found in system PATH: {in_path}")
        for msg in debug_info:
            if msg.startswith("✓"):
                print(f"  {msg}")
        return in_path

    # 3. PyInstaller _MEIPASS (extracted data folder)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, exe_name))
        candidates.append(os.path.join(meipass, "bin", exe_name))
        candidates.append(os.path.join(meipass, "_internal", exe_name))
        candidates.append(os.path.join(meipass, "_internal", "bin", exe_name))
        debug_info.append(f"Checking _MEIPASS: {meipass}")

    # 4. Executable directory
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, exe_name))
        candidates.append(os.path.join(exe_dir, "bin", exe_name))
        candidates.append(os.path.join(exe_dir, "_internal", exe_name))
        candidates.append(os.path.join(exe_dir, "_internal", "bin", exe_name))
        debug_info.append(f"Checking exe dir: {exe_dir}")

    # 5. Project root bin/ (development)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates.append(os.path.join(project_root, "bin", exe_name))
    candidates.append(os.path.join(project_root, exe_name))
    debug_info.append(f"Checking project root: {project_root}")

    for candidate in candidates:
        if os.path.isfile(candidate):
            debug_info.append(f"✓ Found: {candidate}")
            for msg in debug_info:
                if msg.startswith("✓"):
                    print(f"  {msg}")
            return candidate

    # Not found - log all attempts
    print("  ⚠️  FFmpeg resolution failed. Paths checked:")
    for msg in debug_info:
        print(f"  {msg}")
    for candidate in candidates:
        print(f"  ✗ Not found: {candidate}")

    return None


def recorder_worker(name, url, audio_path, work_queue, stop_event, pause_event=None):
    print(f"  🎙️  Gravador iniciado: {name}")

    ffmpeg_cmd = _resolve_ffmpeg_cmd()
    if not ffmpeg_cmd:
        print(
            f"  ⚠️  [{name}] FFmpeg não encontrado. "
            "Instale e adicione ao PATH, defina FFMPEG_PATH, "
            "ou inclua ffmpeg.exe na pasta do executável."
        )
        return

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
            ffmpeg_cmd, "-i", url, "-t", str(RECORD_DURATION),
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
