"""Fabrica de backends LLM segun configuracion."""
import os

OLLAMA_TAGS = {"fast": "qwen2.5:1.5b", "quality": "qwen2.5:3b"}
GGUF_FILES = {
    "fast": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    "quality": "qwen2.5-3b-instruct-q4_k_m.gguf",
}


def get_backend(backend, model, models_dir=None, ollama_url=None):
    """Devuelve un backend listo para extract_invoice_json(text)."""
    if backend == "ollama":
        from .backend_ollama import OllamaBackend
        return OllamaBackend(
            model_id=OLLAMA_TAGS.get(model, OLLAMA_TAGS["fast"]),
            url=ollama_url or "http://127.0.0.1:11434",
        )
    from .backend_embedded import EmbeddedBackend
    path = os.path.join(models_dir or "", GGUF_FILES.get(model, GGUF_FILES["fast"]))
    return EmbeddedBackend(model_path=path)
