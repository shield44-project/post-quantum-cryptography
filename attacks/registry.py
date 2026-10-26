"""The list of attack configurations. One row = one attack id.

cost 'cheap' : weight edits, seconds each, fine on a laptop CPU
cost 'train' : needs training, use a GPU (Colab) if you can
repeats      : independent random draws per model seed (random attacks only)
"""
CARRIER = "features.6.0.weight"


def _cfgs():
    c = []

    def add(attack_id, family, params, cost="cheap", repeats=1):
        c.append({"id": attack_id, "family": family, "params": params, "cost": cost, "repeats": repeats})

    add("none", "control", {})
    for s in (0.01, 0.05, 0.1, 0.2, 0.5):
        add("noise_all_s%g" % s, "noise", {"sigma": s, "scope": "all"}, repeats=3)
    for s in (0.1, 0.5, 1.0):
        add("noise_carrier_s%g" % s, "noise", {"sigma": s, "scope": "carrier"}, repeats=3)
    for p in (0.1, 0.3, 0.5, 0.7, 0.9, 0.95):
        add("prune_global_%g" % p, "prune_global", {"sparsity": p, "scope": "global"})
    for p in (0.3, 0.5, 0.7, 0.9):
        add("prune_layer_%g" % p, "prune_layer", {"sparsity": p, "scope": "layer"})
    add("half", "quantize", {"kind": "half"})
    for b in (8, 6, 4, 3, 2):
        add("quant_pt_%d" % b, "quantize", {"kind": "per_tensor", "bits": b})
    for b in (8, 4):
        add("quant_pc_%d" % b, "quantize", {"kind": "per_channel", "bits": b})
    for m in (2, 10):
        add("rescale_carrier_x%g" % m, "rescale", {"max_scale": m, "scope": "carrier"}, repeats=3)
    add("rescale_all_x10", "rescale", {"max_scale": 10, "scope": "all"}, repeats=3)
    add("permute_out_carrier", "permute", {"which": "out_carrier"}, repeats=3)
    add("permute_in_carrier", "permute", {"which": "in_carrier"}, repeats=3)
    add("permute_all", "permute", {"which": "all"}, repeats=3)
    # ---- training attacks
    for e in (1, 5, 10):
        for lr in (0.001, 0.01):
            add("finetune_e%d_lr%g" % (e, lr), "finetune", {"epochs": e, "lr": lr, "frac": 0.2}, cost="train")
    add("finetune_e10_lr0.05_full", "finetune", {"epochs": 10, "lr": 0.05, "frac": 1.0}, cost="train")
    for p in (0.5, 0.8):
        add("prune_ft_%g" % p, "prune_ft", {"sparsity": p, "epochs": 3, "lr": 0.01, "frac": 0.2}, cost="train")
    for nb in (128, 512):
        add("overwrite_%dbit" % nb, "overwrite",
            {"n_bits": nb, "lam": 20.0, "epochs": 10, "lr": 0.01, "frac": 0.2}, cost="train")
    return c


CONFIGS = _cfgs()
BY_ID = {c["id"]: c for c in CONFIGS}


def select(families=None, cost=None, ids=None):
    out = CONFIGS
    if ids:
        out = [c for c in out if c["id"] in ids]
    if families:
        out = [c for c in out if c["family"] in families]
    if cost:
        out = [c for c in out if c["cost"] == cost]
    return out
