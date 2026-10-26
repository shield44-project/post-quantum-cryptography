"""Load a checkpoint and read the watermark out of it (Phase 3; reused by the Phase 5 verifier)."""
import torch

from embedding.keys import bit_error_rate
from embedding.projection import ProjectionWatermark, get_weight


def load_state_dict(path):
    """Tolerant loader: accepts a raw state_dict, {'state_dict': ...}, or a pickled nn.Module."""
    try:
        obj = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:                      # very old torch without weights_only
        obj = torch.load(path, map_location="cpu")
    except Exception:                      # whole-module pickle written by your own code
        obj = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(obj, torch.nn.Module):
        obj = obj.state_dict()
    if isinstance(obj, dict):
        for k in ("state_dict", "model_state_dict", "model"):
            if k in obj and isinstance(obj[k], dict):
                obj = obj[k]
                break
    return {k.replace("module.", "", 1): v for k, v in obj.items()}


def load_smallcnn(path, width=32):
    from training.model import SmallCNN
    model = SmallCNN(width=width)
    model.load_state_dict(load_state_dict(path))
    model.eval()
    return model


def extract_bits(model, key, layer_name, n_bits, mode="mean"):
    """Return (bits, logits) using the secret key. Works for any model that has `layer_name`."""
    wm = ProjectionWatermark(key, layer_name, n_bits, mode, get_weight(model, layer_name).shape)
    return wm.extract(model)


def report(model, key, layer_name, payload_bits, mode="mean"):
    bits, logits = extract_bits(model, key, layer_name, len(payload_bits), mode)
    errors = sum(int(a != b) for a, b in zip(bits, payload_bits))
    return {
        "bit_errors": errors,
        "ber": bit_error_rate(bits, payload_bits),
        "min_abs_logit": min(abs(z) for z in logits),
        "mean_abs_logit": sum(abs(z) for z in logits) / len(logits),
        "bits": bits,
    }
