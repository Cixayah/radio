import subprocess
import datetime
import os
import numpy as np
import librosa
import torch
import json
import time
import shutil
from pathlib import Path

class AdDetector:
    def __init__(self):
        self.stations = {
          #  "Jovem_Pan": "https://sc1s.cdn.upx.com:9986/stream",
            "Band_FM": "https://stm.alphanetdigital.com.br:7040/band",
            "Ondas_Verdes": "https://live3.livemus.com.br:6922/stream"
        }
        
        self.base_path = "radio_capture"
        self.audio_path = f"{self.base_path}/temp_audios"
        self.log_path = f"{self.base_path}/logs"
        self.ads_path = f"{self.base_path}/detected_ads"
        
        for folder in [self.audio_path, self.log_path, self.ads_path]:
            Path(folder).mkdir(parents=True, exist_ok=True)

        self.model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', 
                                          model='silero_vad', 
                                          trust_repo=True)
        self.get_speech_timestamps = utils[0]

    def record_radio(self, name, url, duration=30):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"{self.audio_path}/{name}_{timestamp}.mp3"
        
        command = [
            'ffmpeg', '-i', url, '-t', str(duration), 
            '-acodec', 'libmp3lame', '-ar', '16000', '-ac', '1',
            file_path, '-y', '-loglevel', 'quiet'
        ]
        
        try:
            subprocess.run(command, check=True, timeout=duration + 15)
            return file_path
        except Exception as e:
            print(f"Error recording {name}: {e}")
            return None

    def analyze_audio(self, file_path):
        try:
            y, sr = librosa.load(file_path, sr=16000)
            wav_tensor = torch.from_numpy(y).float()
            
            with torch.no_grad():
                speech_segments = self.get_speech_timestamps(wav_tensor, self.model, sampling_rate=16000)
            
            duration = len(y) / sr
            total_speech = sum([(s['end'] - s['start']) / 16000 for s in speech_segments])
            speech_ratio = total_speech / duration if duration > 0 else 0
            
            is_ad = False
            reasons = []

            # Thresholds for AD detection
            if speech_ratio > 0.45 or len(speech_segments) > 6:
                is_ad = True
                if speech_ratio > 0.45: reasons.append(f"Speech ratio: {speech_ratio:.1%}")
                if len(speech_segments) > 6: reasons.append(f"Fragments: {len(speech_segments)}")

            return {
                "is_ad": is_ad,
                "speech_ratio": float(speech_ratio),
                "fragments": len(speech_segments),
                "reasons": reasons
            }
        except Exception as e:
            print(f"Analysis failed: {e}")
            return None

    def process_loop(self, interval=10):
        print(f"🚀 Monitoring started. Only Ads will be saved.")
        try:
            while True:
                for name, url in self.stations.items():
                    print(f"--- Checking {name} ---")
                    audio_file = self.record_radio(name, url)
                    
                    if audio_file and os.path.exists(audio_file):
                        result = self.analyze_audio(audio_file)
                        
                        if result and result["is_ad"]:
                            # Save Ad
                            dest = f"{self.ads_path}/AD_{os.path.basename(audio_file)}"
                            shutil.copy2(audio_file, dest)
                            print(f"📢 AD SAVED: {dest} ({result['speech_ratio']:.1%})")
                            self.log_to_file(name, result)
                        else:
                            print(f"🎵 Music/Talk ignored.")
                        
                        # DELETE everything from temp folder after analysis
                        try:
                            os.remove(audio_file)
                        except Exception as e:
                            print(f"Error deleting file: {e}")
                
                print(f"Waiting {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped.")

    def log_to_file(self, station, result):
        log_file = f"{self.log_path}/ads_found_{datetime.datetime.now().strftime('%Y%m%d')}.json"
        entry = {"timestamp": datetime.datetime.now().isoformat(), "station": station, "data": result}
        
        history = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                try: history = json.load(f)
                except: pass
        
        history.append(entry)
        with open(log_file, 'w') as f:
            json.dump(history, f, indent=2)

if __name__ == "__main__":
    detector = AdDetector()
    detector.process_loop(interval=5)