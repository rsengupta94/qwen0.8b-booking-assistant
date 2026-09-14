"""Loads prompt files from prompts/{version}/{kind}/{name}.md and fills their placeholders.

Prompt text lives only in those files. This module substitutes values; it never adds wording.
"""

from functools import lru_cache
from pathlib import Path

import jinja2

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)


def versions() -> list[str]:
    return sorted(p.name for p in PROMPTS_DIR.iterdir() if p.is_dir())


@lru_cache(maxsize=None)
def _template(version: str, kind: str, name: str) -> jinja2.Template:
    path = PROMPTS_DIR / version / kind / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return _env.from_string(path.read_text())


def render(version: str, kind: str, name: str, **values) -> str:
    """kind is "nlu" or "nlg". Missing placeholder values raise, so a prompt never ships half-filled."""
    return _template(version, kind, name).render(**values).strip() + "\n"
