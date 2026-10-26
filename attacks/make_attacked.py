"""Stage A: create attacked copies of your watermarked models (any machine; GPU recommended for 'train' attacks).

    # cheap attacks, laptop CPU is fine
    python -m attacks.make_attacked --cost cheap
    # training attacks, run on Colab
    python -m attacks.make_attacked --cost train
    # control: the same attacks on the UNMARKED baseline models
    python -m attacks.make_attacked --source baseline --cost cheap

Output per attacked model:  runs/attacks/<source>/seed<N>/<attack_id>/rep<R>/{model.pt, attack.json, final.json}
final.json is copied from the watermarked run so that verify_model knows the watermark settings.
Source models are only read, never modified.
"""
import argparse
import json
import shutil
import time
from pathlib import Path

from attacks import registry
from attacks.common import (device, evaluate, load_model, save_model, seed_everything, stable_seed,
                            test_loader, train_loader)
from attacks.train_attacks import finetune, overwrite_watermark, prune_then_finetune
from attacks.weight_attacks import (add_noise, half_roundtrip, permute_channels, prune, quantize,
                                    rescale_channels, sparsity_of)

SOURCES = {
    "wm": "runs/wm_v1/lam20_n256_rs32/seed{seed}",
    "baseline": "runs/baseline/seed{seed}",
}


def apply_attack(cfg, model, seed, layer, dev, data_root):
    """Return (attacked_model, extra_dict)."""
    p, fam = cfg["params"], cfg["family"]
    extra = {}
    if fam == "control":
        return model, extra
    if fam == "noise":
        return add_noise(model, p["sigma"], seed, layer if p["scope"] == "carrier" else None), extra
    if fam in ("prune_global", "prune_layer"):
        out = prune(model, p["sparsity"], p["scope"])
        extra["measured_sparsity"] = sparsity_of(out)
        return out, extra
    if fam == "quantize":
        if p["kind"] == "half":
            return half_roundtrip(model), extra
        return quantize(model, p["bits"], per_channel=(p["kind"] == "per_channel")), extra
    if fam == "rescale":
        return rescale_channels(model, p["max_scale"], seed, layer if p["scope"] == "carrier" else None), extra
    if fam == "permute":
        return permute_channels(model, p["which"], seed, layer), extra
    if fam == "finetune":
        loader = train_loader(p["frac"], seed, data_root)
        return finetune(model, loader, p["epochs"], p["lr"], dev=dev), extra
    if fam == "prune_ft":
        loader = train_loader(p["frac"], seed, data_root)
        out = prune_then_finetune(model, loader, p["sparsity"], p["epochs"], p["lr"], dev=dev)
        extra["measured_sparsity"] = sparsity_of(out)
        return out, extra
    if fam == "overwrite":
        loader = train_loader(p["frac"], seed, data_root)
        out, ber, margin = overwrite_watermark(model, loader, layer, p["n_bits"], p["lam"],
                                               p["epochs"], p["lr"], seed, dev=dev)
        extra["attacker_ber"], extra["attacker_min_abs_logit"] = ber, margin
        return out, extra
    raise ValueError("unknown attack family " + fam)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES), default="wm")
    ap.add_argument("--src-dir", default=None, help="override the folder pattern, must contain {seed}")
    ap.add_argument("--final-from", default=SOURCES["wm"], help="where final.json (watermark settings) is read from")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--width", type=int, default=32)
    ap.add_argument("--layer", default=registry.CARRIER)
    ap.add_argument("--cost", choices=["cheap", "train"], default=None)
    ap.add_argument("--families", nargs="+", default=None)
    ap.add_argument("--ids", nargs="+", default=None)
    ap.add_argument("--out-root", default="runs/attacks")
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfgs = registry.select(args.families, args.cost, args.ids)
    dev = device()
    test = test_loader(args.data_root)
    print("device %s | %d attack configs | seeds %s | source %s" % (dev, len(cfgs), args.seeds, args.source))

    for seed in args.seeds:
        src_dir = Path((args.src_dir or SOURCES[args.source]).format(seed=seed))
        model_path = src_dir / "model.pt"
        final_src = Path(args.final_from.format(seed=seed)) / "final.json"
        if not model_path.exists():
            print("SKIP seed %d: %s not found" % (seed, model_path))
            continue
        if not final_src.exists():
            print("SKIP seed %d: %s not found (needed so verify_model knows the watermark settings)" % (seed, final_src))
            continue
        clean = load_model(model_path, args.width)
        clean_acc = evaluate(clean, test, dev)
        print("\n== %s seed %d: clean accuracy %.4f" % (args.source, seed, clean_acc))

        for cfg in cfgs:
            for rep in range(cfg["repeats"]):
                out_dir = Path(args.out_root) / args.source / ("seed%d" % seed) / cfg["id"] / ("rep%d" % rep)
                if (out_dir / "attack.json").exists() and not args.force:
                    continue
                s = stable_seed(args.source, seed, cfg["id"], rep)
                seed_everything(s)
                t0 = time.time()
                attacked, extra = apply_attack(cfg, clean, s, args.layer, dev, args.data_root)
                acc = evaluate(attacked, test, dev)
                save_model(attacked, str(out_dir / "model.pt"))
                shutil.copy(final_src, out_dir / "final.json")
                meta = {"source": args.source, "seed": seed, "attack_id": cfg["id"], "family": cfg["family"],
                        "params": cfg["params"], "rep": rep, "clean_acc": clean_acc, "attacked_acc": acc,
                        "acc_drop": clean_acc - acc, "layer": args.layer, "seconds": time.time() - t0}
                meta.update(extra)
                (out_dir / "attack.json").write_text(json.dumps(meta, indent=2))
                print("%-26s rep%d  acc %.4f (drop %+.4f)  %.0fs" % (cfg["id"], rep, acc, clean_acc - acc, time.time() - t0),
                      flush=True)


if __name__ == "__main__":
    main()
