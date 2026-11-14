# stage3_audio.py — Piper TTS only
import requests, json, os, sys

BASE_URL = "http://localhost:8080/v1"
TTS_MODEL = "piper-lessac"
PROJECT_DIR = "D:/Lorna/Documents/docker/video_output"
SCRIPT_PATH = os.path.join(PROJECT_DIR, "script.json")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

def generate_audio(idx, narration):
    wav_path = os.path.join(ASSETS_DIR, f"scene_{idx}.wav")
    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
        print(f"  ♻️ scene_{idx}.wav exists, skipping.")
        return True
    print(f"  🔊 Scene {idx+1} TTS...")
    try:
        r = requests.post(f"{BASE_URL}/audio/speech", json={
            "model": TTS_MODEL,
            "input": narration,
        }, timeout=300)
        r.raise_for_status()
        with open(wav_path, "wb") as f:
            f.write(r.content)
        print(f"  ✅ {wav_path} ({os.path.getsize(wav_path)//1024} KB)")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists(SCRIPT_PATH):
        print(f"❌ {SCRIPT_PATH} not found — run stage1 first.")
        sys.exit(1)
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    scenes = data["scenes"]
    print(f"🔊 Generating audio for {len(scenes)} scenes...")
    ok = all([generate_audio(i, s['narration']) for i, s in enumerate(scenes)])
    sys.exit(0 if ok else 1)