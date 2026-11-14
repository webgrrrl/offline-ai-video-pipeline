# stage2_images.py — Stable Diffusion image generation only
import requests, json, os, base64, sys

BASE_URL = "http://localhost:8080/v1"
IMAGE_MODEL = "stablediffusion"
IMAGE_SIZE = "384x576"
PROJECT_DIR = "D:/Lorna/Documents/docker/video_output"
SCRIPT_PATH = os.path.join(PROJECT_DIR, "script.json")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

COLD_TIMEOUT = 1800
WARM_TIMEOUT = 900
_first_image = True

def generate_image(idx, prompt):
    global _first_image
    png_path = os.path.join(ASSETS_DIR, f"scene_{idx}.png")
    if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
        print(f"  ♻️ scene_{idx}.png exists, skipping.")
        return True

    full_prompt = (f"{prompt}, highly detailed, cinematic lighting, "
                   f"vertical composition, no text|blurry, deformed, text, watermark")
    timeout = COLD_TIMEOUT if _first_image else WARM_TIMEOUT
    print(f"  🎨 Scene {idx+1} ({'cold' if _first_image else 'warm'}, timeout={timeout}s)...")

    try:
        r = requests.post(f"{BASE_URL}/images/generations", json={
            "model": IMAGE_MODEL,
            "prompt": full_prompt,
            "size": IMAGE_SIZE,
            "response_format": "b64_json",
        }, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        print(f"  ❌ Timed out after {timeout}s")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return False

    try:
        d = r.json()
    except json.JSONDecodeError:
        print(f"  ❌ Non-JSON response: {r.text[:300]}")
        return False

    if 'data' not in d or not d['data']:
        print(f"  ❌ Bad response: {d}")
        return False

    item = d['data'][0]
    try:
        if 'b64_json' in item:
            with open(png_path, "wb") as f:
                f.write(base64.b64decode(item['b64_json']))
        elif 'url' in item:
            with open(png_path, "wb") as f:
                f.write(requests.get(item['url'], timeout=60).content)
        else:
            print(f"  ⚠️ Unrecognized item: {item}")
            return False
    except Exception as e:
        print(f"  ❌ Save failed: {e}")
        return False

    print(f"  ✅ {png_path} ({os.path.getsize(png_path)//1024} KB)")
    _first_image = False
    return True

if __name__ == "__main__":
    if not os.path.exists(SCRIPT_PATH):
        print(f"❌ {SCRIPT_PATH} not found — run stage1 first.")
        sys.exit(1)
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    scenes = data["scenes"]
    print(f"🎨 Generating images for {len(scenes)} scenes...")
    ok = all([generate_image(i, s['image_prompt']) for i, s in enumerate(scenes)])
    sys.exit(0 if ok else 1)