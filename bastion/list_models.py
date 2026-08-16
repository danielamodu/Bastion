import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("GEMINI_API_KEY")
if not key:
    print("NO KEY")
    exit(1)

req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    models = [m["name"] for m in data.get("models", []) if "gemini" in m["name"]]
    print("Available Gemini models:")
    for m in models:
        print(m)
except Exception as e:
    print("Error:", e)
