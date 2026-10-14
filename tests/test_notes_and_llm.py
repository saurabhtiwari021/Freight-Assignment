import json
import shutil

import pytest

from costwatch import config as C
from costwatch.llm import Ledger, Polisher
from costwatch.notes import load_notes


def test_structured_notes_drift_from_raw_csv_is_caught(tmp_path):
    bad = json.loads(C.NOTES_STRUCTURED_JSON.read_text())
    bad["notes"][0]["applies_to"] = ["Delhi-Jaipur"]            # N001 is really Chennai-Bangalore
    p = tmp_path / "s.json"; p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="scope differs"):
        load_notes(C.NOTES_CSV, p)


def test_structured_notes_missing_id_is_caught(tmp_path):
    bad = json.loads(C.NOTES_STRUCTURED_JSON.read_text()); bad["notes"].pop()
    p = tmp_path / "s.json"; p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="different note ids"):
        load_notes(C.NOTES_CSV, p)


TEMPLATE = "Matches note N002 dated 2025-01-20: festival surcharge. The cost rise has a clear explanation."


def _fake(text):
    calls = []
    def send(payload):
        calls.append(payload)
        assert payload["temperature"] == 0
        return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
    return send, calls


def test_polisher_logs_tokens_and_caches(tmp_path):
    send, calls = _fake("Note N002 (2025-01-20) explains the festival surcharge.")
    led = Ledger(price_in_per_m=1.0, price_out_per_m=2.0)
    p = Polisher("m", send, tmp_path / "c.json", led)
    p.polish(TEMPLATE); p.polish(TEMPLATE)
    assert len(calls) == 1 and led.calls == 1 and led.cache_hits == 1
    assert (led.input_tokens, led.output_tokens) == (100, 20)
    assert led.cost() == pytest.approx((100 * 1 + 20 * 2) / 1e6)


def test_polisher_rejects_a_rewrite_that_invents_or_drops_a_note_id(tmp_path):
    for bad in ("This was caused by N001 flooding.", "Festival surcharge, no id cited."):
        send, _ = _fake(bad)
        led = Ledger()
        out = Polisher("m", send, tmp_path / f"{abs(hash(bad))}.json", led).polish(TEMPLATE)
        assert out == TEMPLATE and led.rejected_rewrites == 1
