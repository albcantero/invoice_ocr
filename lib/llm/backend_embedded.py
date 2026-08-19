"""Backend LLM embebido con llama-cpp-python (por defecto, portable).

El modelo se carga perezoso y se libera con close(): RAM solo al procesar.
llama_cpp se importa dentro de _ensure_model para no exigirla si no se usa.
"""
from .prompt import build_messages


class EmbeddedBackend:
    def __init__(self, model_path, n_ctx=4096, n_threads=None):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self._llm = None

    def _ensure_model(self):
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as error:
                raise RuntimeError(
                    "El backend embebido requiere 'llama-cpp-python'. "
                    "Instala requirements-llm.txt o usa el backend Ollama."
                ) from error
            self._llm = Llama(
                model_path=self.model_path, n_ctx=self.n_ctx,
                n_threads=self.n_threads, verbose=False,
            )
        return self._llm

    def extract_invoice_json(self, text):
        import json
        model = self._ensure_model()
        out = model.create_chat_completion(
            messages=build_messages(text), temperature=0,
            response_format={"type": "json_object"}, max_tokens=2048,
        )
        content = out["choices"][0]["message"]["content"] or "{}"
        return json.loads(content)

    def close(self):
        self._llm = None  # libera el modelo (RAM) al terminar la tanda
