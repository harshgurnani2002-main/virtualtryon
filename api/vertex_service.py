import os
import requests
import time
import io
import base64
from PIL import Image

def _prepare_optimized_image(image_path, max_size=1024, quality=80):
    """
    Optimize image for API transmission:
    1. Resize so the longest dimension is at most max_size.
    2. Compress as JPEG with the given quality.
    3. Return BytesIO buffer.
    """
    try:
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            buffer.seek(0)
            return buffer
    except Exception as e:
        print(f"Image optimization failed for {image_path}: {e}")
        # Return original file if optimization fails
        return open(image_path, "rb")

def _upload_to_imgbb(image_path_or_buffer):
    """Uploads an image to ImgBB and returns the public URL."""
    imgbb_api_key = os.getenv("IMGBB_API_KEY")
    if not imgbb_api_key or "YOUR_CLIENT_API_KEY" in imgbb_api_key:
        raise RuntimeError("IMGBB_API_KEY not set in .env")

    url = f"https://api.imgbb.com/1/upload?expiration=600&key={imgbb_api_key}"
    
    if hasattr(image_path_or_buffer, 'read'):
        image_path_or_buffer.seek(0)
        image_data = image_path_or_buffer.read()
    else:
        with open(image_path_or_buffer, "rb") as f:
            image_data = f.read()

    b64_image = base64.b64encode(image_data).decode('utf-8')
    response = requests.post(url, data={"image": b64_image}, timeout=30)
    
    if response.ok:
        res_json = response.json()
        if res_json.get("success"):
            return res_json["data"]["url"]
        
    raise RuntimeError(f"ImgBB upload failed: {response.text}")

def generate_tryon(person_image_path: str, garment_image_path: str):
    """
    Generate virtual try-on using NanoBananaAPI.ai.
    Uses ImgBB to host images and JSON to interact with NanoBanana.
    """
    api_key = os.getenv("NANOBANANA_API_KEY")
    if not api_key or "YOUR_NANOBANANA_API_KEY" in api_key:
        return {'success': False, 'error': "NANOBANANA_API_KEY not set in .env"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    generate_url = "https://api.nanobananaapi.ai/api/v1/nanobanana/generate"

    try:
        # ── 1. Prepare Binary Image Buffers ──────────────────────────────────
        print("Optimizing images for ImgBB upload...")
        person_buffer = _prepare_optimized_image(person_image_path)
        garment_buffer = _prepare_optimized_image(garment_image_path)

        # ── 2. Upload to ImgBB ───────────────────────────────────────────────
        print("Uploading images to ImgBB...")
        garment_url = _upload_to_imgbb(garment_buffer)
        person_url = _upload_to_imgbb(person_buffer)
        print(f"ImgBB URLs obtained: Garment({garment_url}), Person({person_url})")

        # ── 3. Create Task (POST /generate using JSON) ───────────────────────
        data = {
            "prompt": """Virtual try-on. Generate a high-quality, studio-grade fashion mockup of the person wearing the provided garment.

POSE & FRAMING (STRICT):
- The person MUST face directly toward the camera.
- Eyes looking straight into the camera (front-facing gaze).
- Head aligned forward (no side angle, no profile).
- Body positioned front-facing, symmetrical stance.
- Neutral expression, like a professional e-commerce model.

GARMENT VISIBILITY (CRITICAL):
- Always show the FULL garment completely from top to bottom.
- If the input person image is cropped (face, upper body, or partial), reconstruct and extend to a full-body image.
- Adjust camera framing (zoom out) to ensure full outfit visibility.
- Do NOT crop or cut any part of the clothing.

REALISM:
- Preserve the person’s identity and facial features accurately.
- Maintain realistic proportions and natural posture.
- Ensure proper garment fitting with realistic folds, shadows, and fabric behavior.

STYLE:
- Clean studio background (light grey or white preferred).
- Soft, even lighting with minimal shadows.
- Sharp focus, ultra-realistic, e-commerce photoshoot style.

PRIORITY ORDER:
1. Full garment visibility
2. Front-facing pose looking at camera
3. Realistic identity preservation

FINAL OUTPUT:
- Full-body, front-facing image, person looking directly at the camera, entire garment clearly visible and centered.""",
            "numImages": 1,
            "type": "IMAGETOIAMGE",
            "imageUrls": [
                garment_url,
                person_url
            ],
            "callBackUrl": "https://example.com/callback"
        }

        print(f"Attempting NanoBanana task creation with URLs...")
        
        response = requests.post(generate_url, headers=headers, json=data, timeout=30)
        
        if response.ok:
            result = response.json()
            # Expecting response like: {"code": 200, "msg": "success", "data": {"taskId": "..."}}
            if str(result.get("code")) == "200":
                task_id = result.get("data", {}).get("taskId")
                if task_id:
                    print(f"Task created successfully! ID: {task_id}")
                    # _poll_task doesn't strictly need Content-Type JSON, but it won't hurt
                    return _poll_task(task_id, {"Authorization": f"Bearer {api_key}"})
            
            raise RuntimeError(f"NanoBanana returned an error code: {result}")

        else:
            raise RuntimeError(f"API Error ({response.status_code}): {response.text}")

    except Exception as e:
        print(f"NanoBanana Service Error: {str(e)}")
        return {'success': False, 'error': str(e)}
def _poll_task(task_id, headers):
    status_url = f"https://api.nanobananaapi.ai/api/v1/nanobanana/record-info?taskId={task_id}"
    max_polls = 600
    
    for i in range(max_polls):
        resp = requests.get(status_url, headers=headers, timeout=20)

        if not resp.ok:
            print(f"Polling HTTP error {resp.status_code}. Retrying...")
            time.sleep(5)
            continue

        result = resp.json()

        # 🔥 FIX: handle nested structure
        data = result.get("data", result)

        success_flag = data.get('successFlag', 0)

        if success_flag == 1:
            img_url = data.get('response', {}).get('resultImageUrl', '')
            print(f"✅ Generation successful! Output URL: {img_url}")
            return {'success': True, 'result_url': img_url}

        elif success_flag in (2, 3):
            raise RuntimeError(f"❌ NanoBanana task failed (flag {success_flag})")

        print(f"Polling task {task_id}... Still generating... ({i+1})")
        time.sleep(5)

    raise RuntimeError("Polling timed out")