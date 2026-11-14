# stage1_script.py — Qwen script generation only
import requests, json, sys, os

BASE_URL = "http://localhost:8080/v1"
LLM_MODEL = "qwen2.5-3b"
PROJECT_DIR = "D:/offline-ai-video-pipeline/script/video_output"
SCRIPT_PATH = os.path.join(PROJECT_DIR, "script.json")
os.makedirs(PROJECT_DIR, exist_ok=True)

MAX_ATTEMPTS = 3

def build_prompt(topic, n):
    return f"""You are a video script generator. Create a short vertical video about: {topic}.

The video has exactly {n} scenes:
- Scene 1 is the introduction.
- Scenes 2 to {n-1} are the main points.
- Scene {n} is the conclusion.

You MUST output ONLY a valid JSON object with a single key "scenes" containing an array of EXACTLY {n} objects.
Each object must have exactly two keys: "narration" (max 2 sentences) and "image_prompt" (a detailed visual description, no text in the image).

Output format (replace the placeholders with {n} real scenes; do not copy the count from this example):
{{
  "scenes": [
    {{"narration": "...", "image_prompt": "..."}},
    ... exactly {n} objects total ...
  ]
}}"""

def generate_script(topic, n):
    prompt = build_prompt(topic, n)
    for attempt in range(MAX_ATTEMPTS):
        try:
            res = requests.post(f"{BASE_URL}/chat/completions", json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You output ONLY valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            }, timeout=600)
            if res.status_code != 200:
                print(f"API error {res.status_code}: {res.text}")
                continue
            content = res.json()['choices'][0]['message']['content']
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            scenes = data.get("scenes", [])
            if len(scenes) != n:
                print(f"Attempt {attempt+1}: expected {n} scenes, got {len(scenes)}. Retrying...")
                continue
            if not all(isinstance(s, dict) and 'narration' in s and 'image_prompt' in s for s in scenes):
                print(f"Attempt {attempt+1}: scene missing keys. Retrying...")
                continue
            return scenes
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
    sys.exit(1)

if __name__ == "__main__":
    topic = input("Enter the video topic: ")
    scenenum = int(input("Enter the number of scenes (default is 3): ") or 3)
    if scenenum < 2:
        print("Need at least 2 scenes (intro + conclusion).")
        sys.exit(1)
    print(f"📝  Generating script for: {topic} ({scenenum} scenes)")
    scenes = generate_script(topic, scenenum)
    with open(SCRIPT_PATH, "w", encoding="utf-8") as f:
        json.dump({"topic": topic, "scenes": scenes}, f, indent=2, ensure_ascii=False)
    print(f"✅  Script saved to {SCRIPT_PATH}")
    for i, s in enumerate(scenes):
        print(f"  Scene {i+1}: {s['narration'][:60]}...")
