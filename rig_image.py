#!/usr/bin/env python3
"""
Local image generation on the AI rig (ai-GTi, RTX 3090) via ComfyUI.

Flow: acquire the GPU through gpu-gate over SSH (3 tries then give up so the
caller can fall back to a cloud API), submit a Chroma1-HD workflow to the
ComfyUI API, download the result, release the gate.

Returns a PIL Image or None. None means "use your fallback" — the rig being
busy/off is an expected outcome, not an error.
"""
import json
import random
import subprocess
import time
import urllib.parse
import urllib.request
from io import BytesIO

from PIL import Image

RIG_SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
           "ai@192.168.1.206"]
COMFY_API = "http://192.168.1.206:8188"
GEN_TIMEOUT = 600  # includes first-load of the model into VRAM

NEGATIVE = (
    "This low quality greyscale unfinished sketch is inaccurate and flawed. "
    "The image is very blurred and lacks detail with excessive chromatic "
    "aberrations and artifacts. Photorealistic, muted colors, dull. "
    "The image is covered in text, letters, words, typography, logos, "
    "watermarks and captions."
)


def _workflow(prompt, seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "Chroma1-HD.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "chroma", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "chroma_flux_vae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 1.0, "model": ["1", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["2", 0]}},
        "7": {"class_type": "CFGGuider", "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "cfg": 3.5}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "BasicScheduler", "inputs": {"model": ["4", 0], "scheduler": "beta", "steps": 26, "denoise": 1.0}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1024, "height": 768, "batch_size": 1}},
        "12": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["7", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["11", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "holiday-auto"}},
    }


def _gate(args, timeout):
    try:
        return subprocess.run(RIG_SSH + ["bin/gpu-gate"] + args,
                              capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  ! rig ssh failed: {e}")
        return None


def fetch_rig_image(prompt, label="image-job", tries=3, wait=300):
    """Generate on the rig. None = rig unavailable, caller should fall back."""
    # 1) acquire the GPU (this also evicts llama / starts ComfyUI as needed)
    r = _gate(["acquire", "--for", "comfy", "--tries", str(tries),
               "--wait", str(wait), "--label", label],
              timeout=tries * (wait + 60) + 120)
    if r is None:
        return None
    if r.returncode == 2:
        print("  rig busy after retries -> falling back")
        return None
    if r.returncode != 0:
        print(f"  ! gpu-gate error: {(r.stderr or r.stdout).strip()[:200]}")
        return None

    try:
        # 2) submit
        req = urllib.request.Request(
            COMFY_API + "/prompt",
            json.dumps({"prompt": _workflow(prompt, random.randrange(2**48))}).encode(),
            {"Content-Type": "application/json"})
        pid = json.load(urllib.request.urlopen(req, timeout=30))["prompt_id"]

        # 3) poll
        t0 = time.time()
        while time.time() - t0 < GEN_TIMEOUT:
            time.sleep(3)
            hist = json.load(urllib.request.urlopen(
                COMFY_API + "/history/" + pid, timeout=30))
            entry = hist.get(pid)
            if not entry:
                continue
            if entry.get("status", {}).get("status_str") == "error":
                print("  ! comfy workflow error")
                return None
            for node in entry.get("outputs", {}).values():
                for im in node.get("images", []):
                    url = (COMFY_API + "/view?filename=" + urllib.parse.quote(im["filename"])
                           + "&subfolder=" + urllib.parse.quote(im.get("subfolder", ""))
                           + "&type=" + im.get("type", "output"))
                    data = urllib.request.urlopen(url, timeout=60).read()
                    print(f"  rig image OK in {time.time()-t0:.0f}s")
                    return Image.open(BytesIO(data)).convert("RGB")
        print("  ! rig generation timed out")
        return None
    except Exception as e:
        print(f"  ! rig generation failed: {e}")
        return None
    finally:
        # 4) always release (restores anything gpu-gate evicted)
        _gate(["release"], timeout=120)
