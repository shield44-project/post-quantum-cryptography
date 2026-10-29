"""Attacks that edit weights directly (cheap, no training). Each takes a model and returns a NEW model.

noise      : add Gaussian noise, std = sigma * (std of each weight tensor)
prune      : unstructured magnitude pruning (global threshold, or per layer)
quantize   : simulated uniform symmetric quantization (per tensor or per output channel)
half       : float16 round trip of every parameter
rescale    : function-preserving per-output-channel rescaling of conv + BatchNorm statistics
permute    : function-preserving reordering of channels (neuron permutation)
"""
import math

import torch
import torch.nn as nn

from attacks.common import (carrier_block_index, clone_model, conv_blocks, final_linear,
                            weight_tensors)


# ---------------------------------------------------------------- noise
@torch.no_grad()
def add_noise(model, sigma, seed, carrier_layer=None):
    """carrier_layer=None -> noise on every conv/linear weight; else only on that layer (an informed attacker)."""
    m = clone_model(model)
    g = torch.Generator().manual_seed(seed)
    if carrier_layer is None:
        targets = weight_tensors(m)
    else:
        targets = [dict(m.named_parameters())[carrier_layer]]
    for w in targets:
        noise = torch.randn(w.shape, generator=g) * (sigma * w.detach().float().std().item())
        w.add_(noise.to(w.device, w.dtype))
    return m


# ---------------------------------------------------------------- pruning
@torch.no_grad()
def prune(model, sparsity, scope="global"):
    """Zero the smallest-magnitude weights. scope: 'global' (one threshold) or 'layer' (per tensor)."""
    m = clone_model(model)
    ws = weight_tensors(m)
    if scope == "global":
        allv = torch.cat([w.detach().abs().flatten().cpu() for w in ws])
        k = int(sparsity * allv.numel())
        thr = allv.kthvalue(k).values.item() if k > 0 else -1.0
        for w in ws:
            w.mul_((w.abs() > thr).to(w.dtype))
    elif scope == "layer":
        for w in ws:
            k = int(sparsity * w.numel())
            if k > 0:
                thr = w.detach().abs().flatten().cpu().kthvalue(k).values.item()
                w.mul_((w.abs() > thr).to(w.dtype))
    else:
        raise ValueError("scope must be 'global' or 'layer'")
    return m


def sparsity_of(model):
    ws = weight_tensors(model)
    zeros = sum((w == 0).sum().item() for w in ws)
    return zeros / sum(w.numel() for w in ws)


# ---------------------------------------------------------------- quantization / compression
@torch.no_grad()
def quantize(model, bits, per_channel=False):
    """Symmetric uniform quantize-dequantize of conv/linear weights (BatchNorm left in float, as in most deployments)."""
    if bits < 2:
        raise ValueError("quantize needs at least 2 bits (1 bit leaves no levels and gives NaN weights)")
    m = clone_model(model)
    qmax = 2 ** (bits - 1) - 1
    for w in weight_tensors(m):
        if per_channel:
            maxabs = w.abs().flatten(1).max(dim=1).values.clamp_min(1e-12)
            scale = (maxabs / qmax).view(-1, *([1] * (w.dim() - 1)))
        else:
            scale = w.abs().max().clamp_min(1e-12) / qmax
        w.copy_(torch.clamp(torch.round(w / scale), -qmax, qmax) * scale)
    return m


@torch.no_grad()
def half_roundtrip(model):
    m = clone_model(model)
    for p in m.parameters():
        p.copy_(p.half().float())
    for name, b in m.named_buffers():
        if b.is_floating_point():
            b.copy_(b.half().float())
    return m


# ---------------------------------------------------------------- function-preserving attacks
@torch.no_grad()
def rescale_channels(model, max_scale, seed, layer=None):
    """Multiply conv output channel o by s_o (log-uniform in [1/max_scale, max_scale]) and compensate in
    BatchNorm (running_mean *= s, running_var *= s^2). Eval-mode output is (almost) unchanged,
    but the *unweighted mean over output channels* that carries the watermark changes.
    layer=None -> every block, else only the block containing that conv weight name."""
    m = clone_model(model)
    g = torch.Generator().manual_seed(seed)
    blocks = conv_blocks(m)
    idxs = range(len(blocks)) if layer is None else [carrier_block_index(m, layer)]
    for i in idxs:
        conv, bn = blocks[i]
        c = conv.out_channels
        s = torch.exp((torch.rand(c, generator=g) * 2 - 1) * math.log(max_scale)).to(conv.weight.device)
        conv.weight.mul_(s.view(-1, 1, 1, 1))
        if conv.bias is not None:
            conv.bias.mul_(s)
        bn.running_mean.mul_(s)
        bn.running_var.mul_(s * s)
    return m


@torch.no_grad()
def _permute_block_outputs(model, block_idx, perm):
    """Reorder the output channels of conv block `block_idx` and re-wire whatever consumes them."""
    blocks = conv_blocks(model)
    conv, bn = blocks[block_idx]
    perm = perm.to(conv.weight.device)
    conv.weight.copy_(conv.weight[perm])
    if conv.bias is not None:
        conv.bias.copy_(conv.bias[perm])
    for t in (bn.weight, bn.bias, bn.running_mean, bn.running_var):
        t.copy_(t[perm])
    if block_idx + 1 < len(blocks):                      # next conv reads these channels as its inputs
        nxt = blocks[block_idx + 1][0]
        nxt.weight.copy_(nxt.weight[:, perm])
    else:                                                # classifier: columns are channel-major (c*H*W + s)
        lin = final_linear(model)
        c = conv.out_channels
        w = lin.weight.view(lin.out_features, c, -1)
        lin.weight.copy_(w[:, perm, :].reshape(lin.out_features, -1))


def permute_channels(model, which, seed, layer="features.6.0.weight"):
    """which: 'out_carrier' (reorder the carrier conv's output channels: the mean over them is unchanged),
              'in_carrier'  (reorder the channels feeding the carrier conv: reorders the carrier vector),
              'all'         (random permutation inside every block)."""
    m = clone_model(model)
    g = torch.Generator().manual_seed(seed)
    k = carrier_block_index(m, layer)
    n_blocks = len(conv_blocks(m))
    if which == "out_carrier":
        todo = [k]
    elif which == "in_carrier":
        if k == 0:
            raise ValueError("carrier is the first block; its inputs are image channels")
        todo = [k - 1]
    elif which == "all":
        todo = list(range(n_blocks))
    else:
        raise ValueError("which must be out_carrier, in_carrier or all")
    for b in todo:
        c = conv_blocks(m)[b][0].out_channels
        _permute_block_outputs(m, b, torch.randperm(c, generator=g))
    return m
