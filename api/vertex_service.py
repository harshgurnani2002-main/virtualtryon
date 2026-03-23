# api/vertex_service.py
import os
import base64
import uuid
import requests
import json
from django.conf import settings


def generate_tryon(person_image_path: str, garment_image_path: str):
    """
    Generate virtual try-on using Google Vertex AI REST API.
    Uses the 'virtual-try-on-001' model with base64-encoded images.
    """
    try:
        # ── 1. Read & base64-encode both images ──────────────────────────────
        with open(person_image_path, 'rb') as f:
            person_b64 = base64.b64encode(f.read()).decode('utf-8')

        with open(garment_image_path, 'rb') as f:
            garment_b64 = base64.b64encode(f.read()).decode('utf-8')

        # ── 2. Build OAuth2 access token from service-account key ─────────────
        credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if not credentials_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS is not set")

        import google.auth
        import google.auth.transport.requests
        from google.oauth2 import service_account

        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=scopes
        )
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        access_token = creds.token

        # ── 3. Build the Vertex AI REST request ───────────────────────────────
        project_id = settings.GOOGLE_CLOUD_PROJECT_ID
        location   = settings.GOOGLE_CLOUD_LOCATION   # e.g. "us-central1"

        url = (
            f"https://{location}-aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/{location}/"
            f"publishers/google/models/virtual-try-on-001:predict"
        )

        payload = {
            "instances": [
                {
                    "personImage": {
                        "bytesBase64Encoded": person_b64
                    },
                    "productImages": [
                        {
                            "bytesBase64Encoded": garment_b64
                        }
                    ]
                }
            ],
            "parameters": {
                "imageCount": 1
            }
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # ── 4. Call the API ───────────────────────────────────────────────────
        response = requests.post(url, headers=headers, json=payload, timeout=120)

        if response.status_code != 200:
            error_detail = response.text
            raise RuntimeError(
                f"Vertex AI API error {response.status_code}: {error_detail}"
            )

        resp_json = response.json()

        # ── 5. Extract and save the result image ──────────────────────────────
        predictions = resp_json.get("predictions", [])
        if not predictions:
            raise RuntimeError(
                f"No predictions returned. Full response: {json.dumps(resp_json)}"
            )

        # The API returns a list of dicts; each has 'bytesBase64Encoded'
        result_b64 = predictions[0].get("bytesBase64Encoded")
        if not result_b64:
            raise RuntimeError(
                f"No image bytes in prediction. Keys: {list(predictions[0].keys())}"
            )

        image_bytes = base64.b64decode(result_b64)

        filename = f"tryon_{uuid.uuid4()}.png"
        result_dir = os.path.join(settings.MEDIA_ROOT, 'results')
        os.makedirs(result_dir, exist_ok=True)
        result_path = os.path.join(result_dir, filename)

        with open(result_path, 'wb') as out:
            out.write(image_bytes)

        relative_path = os.path.join('results', filename)

        return {
            'success': True,
            'result_path': relative_path
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }