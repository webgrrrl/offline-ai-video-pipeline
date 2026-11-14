# stage4_render.py — FFmpeg assembly only
import json, os, subprocess, sys

PROJECT_DIR = "D:/offline-ai-video-pipeline/script/video_output"
SCRIPT_PATH = os.path.join(PROJECT_DIR, "script.json")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")

def audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True)
    return float(r.stdout.strip())

def render_clip(png, wav, mp4):
    frames = int(audio_duration(wav) * 30) + 15
    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s=1080x1920:fps=30")
    return subprocess.run(
        ["ffmpeg", "-y", "-i", png, "-i", wav,
         "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
         "-pix_fmt", "yuv420p", "-shortest", "-vf", vf, mp4],
        capture_output=True, text=True)

if __name__ == "__main__":
    if not os.path.exists(SCRIPT_PATH):
        print(f"❌ {SCRIPT_PATH} not found — run stage1 first.")
        sys.exit(1)
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        n = len(json.load(f)["scenes"])

    clips = []
    for i in range(n):
        png = os.path.join(ASSETS_DIR, f"scene_{i}.png")
        wav = os.path.join(ASSETS_DIR, f"scene_{i}.wav")
        mp4 = os.path.join(ASSETS_DIR, f"scene_{i}.mp4")
        if not os.path.exists(png) or not os.path.exists(wav):
            print(f"  ⚠️ Scene {i+1}: missing png or wav, skipping")
            continue
        print(f"  🎞️ Rendering scene {i+1}...")
        r = render_clip(png, wav, mp4)
        if r.returncode != 0:
            print(f"  ❌ ffmpeg failed:\n{r.stderr}")
        else:
            clips.append(mp4)

    if not clips:
        print("❌ No clips to stitch")
        sys.exit(1)

    concat = os.path.join(PROJECT_DIR, "concat_list.txt")
    with open(concat, "w") as f:
        for c in clips:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")

    final = os.path.join(PROJECT_DIR, "final_video.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat,
         "-c", "copy", final],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ Stitch failed:\n{r.stderr}")
        sys.exit(1)
    print(f"✅ Video saved: {final}")
