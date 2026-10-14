"""OPTIONAL wording polish via any OpenAI-compatible endpoint (e.g. Ollama).

Off by default. The LLM can only re-word a reason that verdict.py already built:
the verdict, cited note id and all numbers are decided before it is called, and a
guard rejects any rewrite whose note ids differ from the template. Calls use
temperature 0 + fixed seed, are cached on disk by prompt hash, and every call's
token usage goes to a ledger so one full run can be costed honestly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SYSTEM = ("You rewrite a freight-cost flag explanation in one or two plain-English sentences. "
          "Keep every note id (like N001), every date and every number exactly as given. "
          "Do not add facts, causes or note ids that are not in the input. "
          "If the input says no justification was found, keep that conclusion.")
_NOTE_ID = re.compile(r"\bN\d{3}\b")


@dataclass
class Ledger:
    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    rejected_rewrites: int = 0
    model: str = ""
    price_in_per_m: float = 0.0
    price_out_per_m: float = 0.0
    log: list = field(default_factory=list)

    def cost(self) -> float:
        return (self.input_tokens * self.price_in_per_m + self.output_tokens * self.price_out_per_m) / 1e6

    def as_dict(self) -> dict:
        return {"model": self.model, "llm_calls": self.calls, "cache_hits": self.cache_hits,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "rejected_rewrites": self.rejected_rewrites,
                "price_per_million_in_out": [self.price_in_per_m, self.price_out_per_m],
                "estimated_cost": round(self.cost(), 6)}


def _http_transport(url: str, api_key: str | None):
    def send(payload: dict) -> dict:
        req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {api_key}"} if api_key else {})})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    return send


class Polisher:
    def __init__(self, model: str, transport, cache_path: Path, ledger: Ledger):
        self.model, self.send, self.ledger = model, transport, ledger
        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        ledger.model = model

    @classmethod
    def from_env(cls, cache_path: Path) -> "Polisher | None":
        url, model = os.getenv("COSTWATCH_LLM_URL"), os.getenv("COSTWATCH_LLM_MODEL")
        if not (url and model):
            return None
        ledger = Ledger(price_in_per_m=float(os.getenv("COSTWATCH_PRICE_IN_PER_M", 0)),
                        price_out_per_m=float(os.getenv("COSTWATCH_PRICE_OUT_PER_M", 0)))
        return cls(model, _http_transport(url, os.getenv("COSTWATCH_LLM_KEY")), cache_path, ledger)

    def polish(self, template_reason: str) -> str:
        key = hashlib.sha256(f"{self.model}|{SYSTEM}|{template_reason}".encode()).hexdigest()
        if key in self.cache:
            self.ledger.cache_hits += 1
            out = self.cache[key]
        else:
            resp = self.send({"model": self.model, "temperature": 0, "seed": 0, "max_tokens": 160,
                              "messages": [{"role": "system", "content": SYSTEM},
                                           {"role": "user", "content": template_reason}]})
            out = resp["choices"][0]["message"]["content"].strip()
            usage = resp.get("usage", {})
            self.ledger.calls += 1
            self.ledger.input_tokens += usage.get("prompt_tokens", 0)
            self.ledger.output_tokens += usage.get("completion_tokens", 0)
            self.cache[key] = out
            self.cache_path.write_text(json.dumps(self.cache, indent=1, sort_keys=True))
        if set(_NOTE_ID.findall(out)) != set(_NOTE_ID.findall(template_reason)):
            self.ledger.rejected_rewrites += 1
            return template_reason          # guard: never let new/missing note ids through
        return out
