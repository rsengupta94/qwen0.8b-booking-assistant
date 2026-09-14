"""Single entry point for model calls.

complete(model_id, prompt, schema, params) loads the GGUF named by model_id in
models/registry.json, runs one constrained-decoding call whose output must
match `schema`, and returns the parsed JSON plus latency and token logprobs.

This is the only module allowed to import llama_cpp.
"""

import json
import time
from pathlib import Path

import jinja2
from llama_cpp import Llama, LlamaGrammar

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "models" / "registry.json"

_models: dict[str, Llama] = {}
_templates: dict[str, jinja2.Template] = {}


def _load_registry() -> dict:
    with REGISTRY_PATH.open() as f:
        return json.load(f)


def _get_model(model_id: str) -> Llama:
    if model_id in _models:
        return _models[model_id]
    registry = _load_registry()
    if model_id not in registry:
        raise KeyError(f"model_id {model_id!r} not in {REGISTRY_PATH}")
    gguf_path = REPO_ROOT / registry[model_id]["path"]
    if not gguf_path.is_file():
        raise FileNotFoundError(f"GGUF for {model_id!r} not found at {gguf_path}")
    llm = Llama(
        model_path=str(gguf_path),
        n_ctx=4096,
        n_gpu_layers=-1,  # Metal locally; falls back to CPU where no GPU exists
        logits_all=True,  # needed for per-token logprobs
        verbose=False,
    )
    _models[model_id] = llm
    return llm


def _render_prompt(model_id: str, llm: Llama, prompt: str) -> str:
    """Wrap the prompt in the GGUF's own chat template with thinking mode off."""
    if model_id not in _templates:
        env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)
        _templates[model_id] = env.from_string(llm.metadata["tokenizer.chat_template"])
    return _templates[model_id].render(
        messages=[{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        enable_thinking=False,
        bos_token="",
        eos_token="<|im_end|>",
    )


def complete(model_id: str, prompt: str, schema: dict, params: dict | None = None) -> dict:
    """Run one constrained model call.

    Returns {"output": dict, "raw": str, "latency_ms": int, "logprobs": list}.
    `logprobs` is a list of {"token": str, "logprob": float} for each generated token.
    """
    params = dict(params or {})
    llm = _get_model(model_id)
    grammar = LlamaGrammar.from_json_schema(json.dumps(schema))
    rendered = _render_prompt(model_id, llm, prompt)

    start = time.perf_counter()
    result = llm.create_completion(
        rendered,
        grammar=grammar,
        logprobs=1,
        temperature=params.pop("temperature", 0.0),
        max_tokens=params.pop("max_tokens", 128),
        **params,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)

    choice = result["choices"][0]
    raw = choice["text"]
    output = json.loads(raw)
    lp = choice["logprobs"]
    logprobs = [
        {"token": tok, "logprob": val}
        for tok, val in zip(lp["tokens"], lp["token_logprobs"])
    ]
    return {"output": output, "raw": raw, "latency_ms": latency_ms, "logprobs": logprobs}
