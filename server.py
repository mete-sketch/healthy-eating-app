#!/usr/bin/env python3
"""
Healthy Eating App — API proxy server.

Usage:
    ANTHROPIC_API_KEY=sk-ant-... python3 server.py

Then open http://localhost:3001 in your browser.
"""

import http.server
import json
import os
import urllib.request
import urllib.error
import sys

PORT = int(os.environ.get("PORT", 3001))
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"

# Load API key from .env file or environment variable
def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key.strip()
    # Try reading from .env file in the same directory
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""

API_KEY = load_api_key()
if not API_KEY or API_KEY == "paste-your-key-here":
    print("\n  Missing Anthropic API key!")
    print("  Edit the .env file in this folder and paste your key:\n")
    print("    ANTHROPIC_API_KEY=sk-ant-your-actual-key\n")
    print("  Get your key at: https://console.anthropic.com/settings/keys\n")
    sys.exit(1)

SYSTEM_PROMPT = """You are a friendly, supportive nutrition advisor embedded in a healthy eating app. The user will tell you a food they're thinking of eating. Analyse it and respond with ONLY valid JSON (no markdown, no code fences) in this exact format:

{
  "food": "<the food name, cleaned up>",
  "rating": <number 1-10>,
  "portion": "<recommended portion in everyday visual terms, e.g. 'about the size of your fist', 'a deck of cards worth'>",
  "calories": "<calorie estimate for that portion, e.g. '~350 calories'>",
  "explanation": "<2-3 sentences explaining the rating in a casual, supportive tone. Never shame. Be encouraging.>",
  "alternative": "<if rating < 6, suggest a healthier swap in 1 sentence. If rating >= 6, set to null>"
}

Guidelines:
- Be encouraging and positive, never judgmental
- Use everyday language, not clinical terms
- Portion sizes should use visual comparisons (fist, palm, deck of cards, tennis ball, etc.)
- Calorie estimates should be approximate and use the ~ symbol
- For healthy foods (7+), celebrate the choice
- For moderate foods (4-6), acknowledge it's okay and gently suggest improvements
- For less healthy foods (1-3), be kind — suggest it as an occasional treat and offer a swap
- The alternative field should be null (not a string "null") when rating >= 6"""

IMAGE_SYSTEM_PROMPT = """You are a friendly, supportive nutrition advisor embedded in a healthy eating app. The user has sent a PHOTO of food. Your job is to:

1. Identify the food in the image
2. Estimate the ACTUAL portion size visible in the photo (use visual cues like plate size, utensils, hands, or common dish sizes to judge)
3. Calculate calories and macros based on THAT specific portion — not a generic serving

Respond with ONLY valid JSON (no markdown, no code fences) in this exact format:

{
  "food": "<the food name, cleaned up>",
  "rating": <number 1-10>,
  "portion": "<your estimate of the actual portion shown, e.g. 'about 1.5 cups / a large bowlful', 'roughly 200g / palm-sized piece'>",
  "calories": "<calorie estimate for the portion SHOWN in the photo, e.g. '~450 calories'>",
  "protein": "<estimated protein in grams, e.g. '~25g'>",
  "carbs": "<estimated carbs in grams, e.g. '~40g'>",
  "fat": "<estimated fat in grams, e.g. '~18g'>",
  "explanation": "<2-3 sentences explaining the rating AND how you estimated the portion from the photo. Be casual and supportive. Never shame.>",
  "alternative": "<if rating < 6, suggest a healthier swap in 1 sentence. If rating >= 6, set to null>"
}

Guidelines:
- Be encouraging and positive, never judgmental
- Use everyday language, not clinical terms
- CAREFULLY estimate the portion visible in the photo — look at plate/bowl size, compare to utensils, hands, or standard dish dimensions
- Give a specific calorie number based on what you SEE, not a generic serving
- Include protein, carbs, and fat estimates for the visible portion
- For healthy foods (7+), celebrate the choice
- For moderate foods (4-6), acknowledge it's okay and gently suggest improvements
- For less healthy foods (1-3), be kind — suggest it as an occasional treat and offer a swap
- The alternative field should be null (not a string "null") when rating >= 6"""

VALID_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_BODY_SIZE = 10_000_000  # 10MB


def _send_to_anthropic(payload_dict: dict) -> dict:
    """Send a request to the Anthropic API and return the parsed JSON response."""
    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("content", [{}])[0].get("text", "")
            return json.loads(text)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("message", f"API error: {e.code}")
        except json.JSONDecodeError:
            msg = f"API error: {e.code}"
        raise Exception(msg)


def call_anthropic(food: str) -> dict:
    return _send_to_anthropic({
        "model": MODEL,
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": f"Analyse this food: {food}"}],
    })


def call_anthropic_image(image_base64: str, media_type: str) -> dict:
    return _send_to_anthropic({
        "model": MODEL,
        "max_tokens": 1000,
        "system": IMAGE_SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
                {
                    "type": "text",
                    "text": "What food is in this photo? Estimate the actual portion size you can see and calculate the calories and macros for that specific amount.",
                },
            ],
        }],
    })


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"  {args[0]}")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        # Serve the HTML file
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(script_dir, "index.html")
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/analyze":
            self._handle_analyze_text()
        elif self.path == "/api/analyze-image":
            self._handle_analyze_image()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def _handle_analyze_text(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            food = data.get("food", "").strip()

            if not food:
                self._send_json(400, {"error": "Please provide a food to analyse."})
                return

            print(f'  Analysing: "{food}"')
            result = call_anthropic(food)
            print(f"  -> Rating: {result.get('rating', '?')}/10")
            self._send_json(200, result)

        except Exception as e:
            print(f"  Error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_analyze_image(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_BODY_SIZE:
                self._send_json(413, {"error": "Image is too large. Please try a smaller photo."})
                return

            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            image = data.get("image", "")
            media_type = data.get("media_type", "")

            if not image or not media_type:
                self._send_json(400, {"error": "Please provide an image to analyse."})
                return

            if media_type not in VALID_IMAGE_TYPES:
                self._send_json(400, {"error": f"Unsupported image type: {media_type}"})
                return

            print(f"  Analysing photo ({media_type})...")
            result = call_anthropic_image(image, media_type)
            print(f"  -> Food: {result.get('food', '?')}, Rating: {result.get('rating', '?')}/10")
            self._send_json(200, result)

        except Exception as e:
            print(f"  Error: {e}")
            self._send_json(500, {"error": str(e)})


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), RequestHandler)
    print(f"\n  Healthy Eating App server running!")
    print(f"  Open in your browser: http://localhost:{PORT}")
    print(f"  On iPhone (same Wi-Fi): http://<your-mac-ip>:{PORT}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()
