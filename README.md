# Offline AI Video Pipeline: Setup Guide (LocalAI + Docker, 16GB RAM)

This guide takes you from zero to a working offline video pipeline using AI, and is part of my upcoming [blog post](https://webgrrrl.net) on challenges of setting up a local LLM using Docker.

Qwen writes the script for each scene, Stable Diffusion generates images for the scenes, Piper narrates based on each scene, and FFmpeg assembles the scenes into a video. It does **not** assume you have unlimited memory, and it does not pretend that "just pull the Docker image and it works." Every step reflects a configuration or pitfall that was actually encountered on a 16GB machine.

---

## Prerequisites

- Docker Desktop installed and running
- At least 20GB of free disk space (models + container images)
- 16GB RAM (this guide is optimised for this ceiling; more memory is better, but 16GB is viable)
- Python 3.10+ installed on the host, with the `requests` package
- FFmpeg installed on the host and added to PATH
- A bash shell to run `run-all.sh` and the `curl` tests (Git Bash or WSL on Windows)

---

## Step 1: Create the Directory Structure -- stay connected to the Internet

`git clone` this repo to your preferred path. In this example, I use `D:/`.
Then, create the following folders on your host (adjust the `D:/offline-ai-video-pipeline/` path to your preference):

```text
D:/offline-ai-video-pipeline/
├── models/                  # Model files (GGUF for Qwen and SD, ONNX for Piper) + YAML configs
├── backend_data/            # Persistent backend binaries (avoids re-download)
├── script/                  # Python scripts and generated assets are stored here
└── docker-compose-localai.yaml
```

**Why `backend_data` matters**: LocalAI's CPU image bundles `llama-cpp` and `stablediffusion-ggml`, but other backends are not bundled. Mounting this path ensures any backend you install can survive container recreation.

---

## Step 2: Write the Compose File

Create `docker-compose-localai.yaml`:

```yaml
name: ai-video-studio

services:
  localai:
    # Tip: pin a specific version tag instead of latest-cpu for reproducible results
    image: localai/localai:latest-cpu
    container_name: localai-studio
    ports:
      - "8080:8080"
    volumes:
      - D:/offline-ai-video-pipeline/models:/build/models
      - D:/offline-ai-video-pipeline/backend_data:/tmp/localai/backend_data
    environment:
      - THREADS=8
      - LOCALAI_DISABLE_PRELOAD=true
      - LOCALAI_DISABLE_GUESSING=true
      - LOCALAI_WATCHDOG_IDLE=true
      - LOCALAI_WATCHDOG_IDLE_TIMEOUT=5m
      - LOCALAI_MAX_ACTIVE_BACKENDS=1
    mem_limit: 11g
    restart: unless-stopped
```

**Critical detail**: The mount path must be `/build/models`, not `/models`. The CPU image expects the former; mounting the latter results in only previously registered models appearing, and new files will be ignored.

---

## Step 3: Download Models

Each model uses a different file format. Do not mix them up:

| Model | Format | Files |
|---|---|---|
| Qwen 2.5-3B (LLM) | GGUF | one `.gguf` file |
| Stable Diffusion 1.5 (images) | GGUF | one `.gguf` file |
| Piper (text-to-speech) | **ONNX** (not GGUF) | `.onnx` **and** `.onnx.json` |

### Qwen 2.5-3B (LLM)

Download the GGUF from Hugging Face (`Qwen/Qwen2.5-3B-Instruct-GGUF`, choose Q4_K_M or similar quantisation). Place it in `models/`.

Create `qwen2.5-3b.yaml`:

```yaml
name: qwen2.5-3b
backend: llama-cpp
parameters:
  model: qwen2.5-3b-instruct-q4_k_m.gguf
```

The `model` value must match the downloaded filename exactly, including lowercase letters, because the container runs on Linux, where filenames are case-sensitive.

### Stable Diffusion 1.5 (Images)

Download `v1-5-pruned_Q8_0.gguf` from `kostakoff/stable-diffusion-v1-5-GGUF`. Place it in `models/`.

Create `stablediffusion.yaml`:

```yaml
name: stablediffusion
backend: stablediffusion-ggml
parameters:
  model: v1-5-pruned_Q8_0.gguf
  step: 20
  width: 384
  height: 576
```

**Do not use the LocalAI gallery to install SD.** The OCI reference parsing within LocalAI often fails. Manual download + YAML is the reliable path.

### Piper (TTS)

Piper uses **ONNX** voice models, not GGUF. Download `en_US-lessac-medium.onnx` **and** `en_US-lessac-medium.onnx.json` from the Piper voices repository, and place both in `models/`. Both files are mandatory; the backend fails without the JSON companion.

Create `piper-lessac.yaml`:

```yaml
name: piper-lessac
backend: piper
parameters:
  model: en_US-lessac-medium.onnx
  language: en_US
```

(Adding for awareness: I may have missed a step here, so I'll add later. For the first run, Piper may download language and voice libraries, and you're required still have Internet connection at this point. I vaguely recalled that, once the libraries are downloaded, I copied everything under `/tmp/localai/backend_data` from Docker's `Files` into `D:\docker\backend_data\`, but I can't be sure exactly. This needed to be done, otherwise if you decide to stop/restart/delete the container, everything under `/tmp/localai/backend_data` will disappear and reset itself.)

---

## Step 4: Start the Container and Verify

Download the `localai/localai:latest-cpu` image from Docker Hub if you haven't done so.
Then, run the following bash commands.

```bash
cd D:/offline-ai-video-pipeline/
docker compose -f docker-compose-localai.yaml up -d
```

You can check the `localai-studio` container logs to see whether the startup is complete.
Then test to see if LocalAI can detect the models in your local computer.

```bash
curl http://localhost:8080/v1/models
```

You should see `qwen2.5-3b`, `stablediffusion`, and `piper-lessac` in the response. If any are missing, check the YAML filename of each model and the `name` field inside it.

---

## Step 5: Smoke-Test Each Model Individually

**Do not skip this.** Running a full pipeline before each model is verified independently is how you end up debugging three things at once.

### Test LLM

```bash
curl http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen2.5-3b",
  "messages": [{"role":"user","content":"Reply with exactly: OK"}],
  "max_tokens": 10
}'
```

Expect a JSON response with `"content"` containing `OK`.

### Test SD (Stable Diffusion)

```bash
time curl -X POST http://localhost:8080/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"model":"stablediffusion","prompt":"a red apple","size":"384x576","response_format":"b64_json"}' \
  --output sd_test.json
```

You can monitor the memory usage under Docker Desktop's `Stats`, or run `docker stats localai-studio` in a separate terminal. Peak should stay under ~10GB. Expect 2–3 minutes on CPU.

### Test Piper

```bash
curl -X POST http://localhost:8080/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"piper-lessac","input":"This is a test."}' \
  --output test.wav
ls -la test.wav
```

Expect 50–200KB. If you get a tiny file (under 1KB), the request failed. Check the container logs for `unsupported model type` or `EOF`, and confirm that both the `.onnx` and `.onnx.json` files are present in `models/`.

---

## Step 6: Write the Four Pipeline Scripts  -- start going offline and run locally

### `stage1_script.py` — Qwen Only

Reads a topic, generates a JSON script with N scenes, writes `script.json`. **Important**: the prompt must not contain contradictory counts. If you ask for "5 scenes" but the example shows 2, Qwen 2.5-3B will produce 0 scenes. Use placeholders in the example, or omit the example entirely.

```python
# Key excerpt: validation must compare to the requested count, not a hardcoded 3
if len(scenes) != scenenum:
    print(f"Attempt {attempt+1}: expected {scenenum}, got {len(scenes)}. Retrying...")
    continue
```

### `stage2_images.py` — SD Only

Reads `script.json`, generates `scene_N.png` for each missing image. Tracks a `_first_image` flag to use `COLD_TIMEOUT = 1800` for the first request and `WARM_TIMEOUT = 900` for subsequent ones. Skips existing PNGs so re-runs are cheap.

### `stage3_audio.py` — Piper Only

Reads `script.json`, generates `scene_N.wav`. Omits the `voice` parameter in the request body. The model ID already encodes the voice, and passing `voice` can cause errors on some backend versions.

### `stage4_render.py` — FFmpeg Only

Reads scene count from `script.json`, renders each PNG+WAV pair with a Ken Burns effect (`zoompan`), scales to 1080×1920, and concatenates via `concat_list.txt`. No LocalAI involvement.

---

## Step 7: The Orchestration Script

Create `run-all.sh` and save it in the same directory as your other scripts (in this example, I save this under `script`:

```bash
#!/usr/bin/env bash
set -e

COMPOSE_FILE="D:/offline-ai-video-pipeline/docker-compose-localai.yaml"

# Wait until LocalAI answers, so the next stage does not start too early
wait_for_localai() {
  until curl -sf http://localhost:8080/v1/models > /dev/null; do
    sleep 3
  done
}

docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d
wait_for_localai
python stage1_script.py

docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d
wait_for_localai
python stage2_images.py

python stage3_audio.py
python stage4_render.py

echo "Pipeline complete. Check final_video.mp4"
```

**Why `down && up` instead of `restart`**: A restart sends SIGTERM and reuses the same container. Usually this releases memory, but shared memory leaks or zombie backend processes can survive. `down` removes the container entirely, guaranteeing zero residual memory before SD loads. It only takes a few seconds and eliminates the class of `EOF` errors described below.

**Why no restart between stage 2 and stage 3**: Piper's memory footprint is negligible, so it loads without trouble after the image stage.

---

## Common Failures You Will Encounter (and Fixes)

| Symptom | Cause | Fix |
|---|---|---|
| `/v1/models` shows only Piper | Mount path is `/models`, not `/build/models` | Correct the volume mount |
| SD returns `rpc error: code = Unavailable desc = error reading from server: EOF` | Qwen still resident; SD cannot allocate | Restart container before stage 2 |
| TTS returns `backend not found` | The `crispasr` model variant was installed, but its backend is not in the container | Use the native `piper` backend with an `.onnx` voice |
| TTS returns `should end with .onnx` | The native `piper` backend rejects GGUF files; it only loads ONNX voices | Download the `.onnx` voice + `.onnx.json` |
| TTS returns tiny file | Missing `.onnx.json` companion | Download both files into `models/` |
| Qwen returns 0 scenes | Contradictory prompt ("5 in array" but "7 total") | Make counts consistent; use placeholders in example |
| Qwen model not listed, or fails to load | `model:` in the YAML does not match the filename (case-sensitive) | Match the filename exactly |
| SD gallery install fails with `could not parse reference` | Known OCI parsing issue | Manual download + YAML |

---

## Final Architecture Summary

```text
Stage 1 (Qwen)   → script.json    → Container restart
Stage 2 (SD)     → scene_N.png    → (no restart)
Stage 3 (Piper)  → scene_N.wav    → (no restart)
Stage 4 (FFmpeg) → final_video.mp4
```

**Memory behaviour**: Qwen uses ~2GB during stage 1. SD uses ~7–9GB during stage 2. Piper uses negligible memory. FFmpeg runs on the host, not in the container. The 11GB `mem_limit` is a safety net, not a target. You should see peak memory comfortably below it when the stages are separated.

**Time budget** (cold start): Script generation ~25–40s, each image ~2–3 min, TTS ~1s per scene, rendering ~1–3 min. Total ~10–15 minutes for a 3-scene video.

All configuration files and Python scripts are available in the GitHub repository: https://github.com/webgrrrl/offline-ai-video-pipeline. The only external dependencies are Docker, Python `requests`, and FFmpeg. Everything else (models, backends, inference) runs offline once the models are downloaded.
