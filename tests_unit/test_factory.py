from lib.llm.factory import OLLAMA_TAGS, GGUF_FILES, get_backend


def test_model_maps():
    assert OLLAMA_TAGS["fast"] == "qwen2.5:1.5b"
    assert OLLAMA_TAGS["quality"] == "qwen2.5:3b"
    assert GGUF_FILES["fast"].endswith(".gguf")
    assert GGUF_FILES["quality"].endswith(".gguf")


def test_get_backend_ollama_type():
    b = get_backend(backend="ollama", model="fast", ollama_url="http://127.0.0.1:11434")
    assert b.__class__.__name__ == "OllamaBackend"
    assert b.model_id == "qwen2.5:1.5b"
