"""Backend LLM contra Ollama en localhost (para desarrollo y alternativa)."""
import json
import urllib.request

from .prompt import build_messages


class OllamaBackend:
    def __init__(self, model_id, url="http://127.0.0.1:11434", timeout=240):
        self.model_id = model_id
        self.url = url.rstrip("/")
        self.timeout = timeout

    def extract_invoice_json(self, text):
        payload = {
            "model": self.model_id, "stream": False, "format": "json",
            "keep_alive": "30s",
            "options": {"temperature": 0, "num_predict": 2048},
            "messages": build_messages(text),
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url + "/api/chat", data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body.get("message", {}).get("content", "") or "{}"
        return json.loads(content)

    def close(self):
        pass
