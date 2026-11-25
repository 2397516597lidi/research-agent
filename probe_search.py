import os
import json
import requests

KEY = os.getenv("DEEPSEEK_API_KEY")
resp = requests.post(
    "https://api.deepseek.com/v1/tools/search",
    headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    json={"query": "企业级 AI Agent 落地 2026", "count": 5, "need_content": True},
    timeout=60,
)
resp.raise_for_status()
data = resp.json()

print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])