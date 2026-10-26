"""Bridge to your Phase 5 verifier (LOCAL, needs liboqs).

The attacked model is verified by running your own tool, exactly as an auditor would:

    python -m verify.verify_model --model <attacked model.pt>

and parsing what it prints. A copy of final.json sits next to every attacked model.pt
so the verifier reads the same watermark settings as for the clean model.

Optionally, a 'probe' measures the raw channel error (fraction of codeword values whose sign flipped
before error correction). The probe switches itself off unless it can reproduce the verifier's own
'min margin' on the clean model, so it can never report numbers from a wrong projection matrix.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

_CHECK = re.compile(r"^(PASS|FAIL)\s+(.*)$")
_SETTINGS = re.compile(r"ecc\s+(\S+)\s*\|\s*n_bits\s+(\d+)\s*\|\s*layer\s+(\S+)\s*\|\s*mode\s+(\S+)")


def parse_verifier_output(text: str) -> dict:
    """Turn the verifier's printed report into a dict. Tolerant: missing fields become None."""
    out = {"verdict": None, "checks": [], "wm_read": None, "payload_match": None,
           "min_margin": None, "corrected": None, "erasures": None, "n_values": None,
           "ecc": None, "n_bits": None, "layer": None, "mode": None}
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        s = _SETTINGS.search(ln)
        if s and "watermark settings" in ln:
            out["ecc"], out["n_bits"], out["layer"], out["mode"] = s.group(1), int(s.group(2)), s.group(3), s.group(4)
        m = _CHECK.match(ln.strip())
        if m:
            status, rest = m.group(1), m.group(2)
            out["checks"].append((status, rest))
            if rest.startswith("watermark read"):
                out["wm_read"] = status
                for key, rx in (("min_margin", r"min margin\s+(-?[\d.]+)"), ("corrected", r"corrected\s+(\d+)"),
                                ("erasures", r"erasures\s+(\d+)"), ("n_values", r"(\d+)\s+values")):
                    f = re.search(rx, rest)
                    if f:
                        out[key] = float(f.group(1)) if key == "min_margin" else int(f.group(1))
            elif rest.startswith("extracted payload"):
                out["payload_match"] = status
    if lines and lines[-1].strip() in ("VERIFIED", "REJECTED"):
        out["verdict"] = lines[-1].strip()
    return out


def run_verifier(model_path, python=None, cwd=".", timeout=300, extra_args=None) -> dict:
    """Run verify_model on one checkpoint and return the parsed report (verdict 'ERROR' if it crashed)."""
    cmd = [python or sys.executable, "-m", "verify.verify_model", "--model", str(model_path)] + list(extra_args or [])
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"verdict": "ERROR", "error": "timeout"}
    rep = parse_verifier_output(p.stdout)
    rep["returncode"] = p.returncode
    if rep["verdict"] is None:
        rep["verdict"] = "ERROR"
        rep["error"] = (p.stderr or p.stdout)[-400:]
    return rep


class Probe:
    """Raw (pre-ECC) sign-flip rate of the watermark logits relative to the clean model."""

    def __init__(self, enabled, reason, X=None, layer=None, clean_signs=None):
        self.enabled, self.reason, self.X, self.layer, self.clean_signs = enabled, reason, X, layer, clean_signs

    @staticmethod
    def _logits(state, layer, X):
        import torch
        w = state[layer].float()
        v = w.mean(dim=0).flatten()
        return (torch.from_numpy(X) @ v).numpy()

    @classmethod
    def from_clean(cls, clean_model_path, clean_report, key_path="keys/watermark_key.bin"):
        try:
            import numpy as np
            from attacks.common import load_state_dict
            from embedding.keys import load_key, projection_matrix_np
            layer, n_values = clean_report.get("layer"), clean_report.get("n_values")
            if clean_report.get("mode") != "mean" or not layer or not n_values or clean_report.get("min_margin") is None:
                return cls(False, "verifier report lacks layer/values/margin or mode is not 'mean'")
            state = load_state_dict(clean_model_path)
            dim = int(state[layer].shape[1] * np.prod(state[layer].shape[2:]))
            X = projection_matrix_np(load_key(key_path), layer, n_values, dim)
            z = cls._logits(state, layer, X)
            mine = float(np.abs(z).min())
            if abs(mine - clean_report["min_margin"]) > max(0.02, 0.01 * clean_report["min_margin"]):
                return cls(False, "could not reproduce the verifier's margin (mine %.3f vs %.3f); raw flip rate disabled"
                           % (mine, clean_report["min_margin"]))
            return cls(True, "reproduced verifier margin %.3f" % mine, X, layer, np.sign(z))
        except Exception as e:  # any import/shape problem -> disable, never crash the evaluation
            return cls(False, "probe disabled: %s" % e)

    def flip_rate(self, model_path):
        if not self.enabled:
            return None
        import numpy as np
        from attacks.common import load_state_dict
        z = self._logits(load_state_dict(model_path), self.layer, self.X)
        return float((np.sign(z) != self.clean_signs).mean())
