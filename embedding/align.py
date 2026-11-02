"""Undo channel permutations and measure partial evidence (Phase 6b).

Permutation attack (Phase 6): reorder the output channels of the block that feeds the carrier conv and the carrier's
input channels to match. The network computes exactly the same function, but the carrier vector v ("mean" mode:
in_channels blocks of k*k numbers) has its blocks reordered, so X @ v is noise and the watermark reads as random.

Re-alignment: the verifier knows the secret matrix X and the codeword it expects (from the signed manifest), so it
can ask which block order makes X @ v agree best with that codeword. With s = 2 * codeword - 1 (+1 / -1):

    score(pi) = sum_j s_j * (X @ v_pi)_j = sum_c  A_c . v_pi(c),     A = (X^T s) reshaped to (in_channels, k*k)

The score is a sum over channel slots, so the best pi is a linear assignment problem, solved exactly by the
Hungarian algorithm (scipy.optimize.linear_sum_assignment). On an unpermuted marked model the answer is the
identity; on a permuted one it is the inverse permutation; on an unmarked model it cannot conjure 256 correct
payload bits (see tests/test_phase6b.py and docs/phase6b_results.md for the measured false-accept rate).

Partial evidence (overwrite attack): an attacker who fine-tunes a second watermark into the same layer flips some
code values, often more than Reed-Solomon can repair, yet most still agree with the signed codeword. For a model
that never carried it, agreement is Binomial(n, 1/2), so k or more agreements has probability P(Bin(n, 1/2) >= k).
The threshold is only ever applied in the model's own channel order: searching over orders would inflate it.
"""
import math

import numpy as np

EVIDENCE_LOG2_P = -64          # "damaged but present" needs a chance agreement probability below 2^-64


def carrier_blocks(weight_shape):
    """(in_channels, k*k) for a conv weight (out, in, kh, kw) in 'mean' mode."""
    k = 1
    for s in weight_shape[2:]:
        k *= s
    return int(weight_shape[1]), k


def align_permutation(X, v, codeword, weight_shape):
    """Best block order for v. Returns (perm, moved): v_aligned = v.reshape(C, K)[perm].ravel(); moved = blocks not in place."""
    from scipy.optimize import linear_sum_assignment

    C, K = carrier_blocks(weight_shape)
    X = np.asarray(X, dtype=np.float64)
    V = np.asarray(v, dtype=np.float64).reshape(C, K)
    s = 2.0 * np.asarray(codeword, dtype=np.float64) - 1.0
    A = (X.T @ s).reshape(C, K)                 # what slot c "wants" to see
    gain = A @ V.T                              # gain[c, d] = score of putting block d in slot c
    slots, blocks = linear_sum_assignment(gain, maximize=True)
    perm = np.empty(C, dtype=int)
    perm[slots] = blocks
    return perm, int((perm != np.arange(C)).sum())


def apply_permutation(v, perm, weight_shape):
    C, K = carrier_blocks(weight_shape)
    return np.asarray(v, dtype=np.float64).reshape(C, K)[perm].ravel()


def recover_scales(X, v, codeword, weight_shape, floor=1e-3):
    """Undo per-input-channel positive scaling (the scaling half of neural structural obfuscation).

    Scaling channel c of the previous block by s_c > 0 (in its BatchNorm) and the carrier's input weights by 1/s_c
    leaves the network's function unchanged (ReLU and MaxPool commute with positive scaling) but turns the carrier
    blocks v_c into v_c / s_c. Find a_c > 0 so that the code values of sum_c a_c X_c v_c all read as the codeword,
    with the largest worst-case margin (a linear program). Returns (v_rescaled, margin); margin > 0 = all fitted.

    Why this cannot make an unmarked model pass: 64 positive factors realise at most about 2^275 of the 2^512 sign
    patterns of 512 code values (Cover's function-counting theorem), so fitting a codeword the model never carried has
    probability about 2^-237. A marked model that was scaled is fitted by the true factors with its original margin.
    """
    from scipy.optimize import linprog

    C, K = carrier_blocks(weight_shape)
    X = np.asarray(X, dtype=np.float64)
    V = np.asarray(v, dtype=np.float64).reshape(C, K)
    s = 2.0 * np.asarray(codeword, dtype=np.float64) - 1.0
    G = np.einsum("jck,ck->jc", X.reshape(-1, C, K), V) * s[:, None]    # G[j, c] = s_j * (X_c . v_c)
    G = G / max(np.abs(G).max(), 1e-12)
    # variables a_1..a_C, t ; maximise t  s.t.  t - G a <= 0,  sum a = C,  a >= floor
    c_obj = np.zeros(C + 1)
    c_obj[-1] = -1.0
    A_ub = np.hstack([-G, np.ones((G.shape[0], 1))])
    res = linprog(c_obj, A_ub=A_ub, b_ub=np.zeros(G.shape[0]), A_eq=np.hstack([np.ones((1, C)), [[0.0]]]),
                  b_eq=[float(C)], bounds=[(floor, None)] * C + [(None, None)], method="highs")
    if res.status != 0:
        return None, float("-inf")
    a = res.x[:C]
    return (V * a[:, None]).ravel(), float(res.x[-1])


def log2_cover_fraction(n, d):
    """log2 of the share of the 2^n sign patterns of n points that a d-dimensional linear map through the origin can
    realise (Cover 1965): 2 * sum_{k<d} C(n-1, k) / 2^n. This bounds the chance that free per-channel factors fit a
    random codeword."""
    if d >= n:
        return 0.0
    terms = [math.lgamma(n) - math.lgamma(k + 1) - math.lgamma(n - k) for k in range(d)]
    m = max(terms)
    return min(0.0, (math.log(2) + m + math.log(sum(math.exp(t - m) for t in terms))) / math.log(2) - n)


def undo_is_safe(n_values, weight_shape, log2_p=EVIDENCE_LOG2_P):
    """The permutation / scaling search may only run when the code is long enough that fitting a codeword the model
    never carried is provably negligible: with 512 values and 64 channels the bound is 2^-237; with a legacy 32-value
    code and 16 channels it is about 1, i.e. the search would fit anything, so it is refused."""
    C, _ = carrier_blocks(weight_shape)
    return log2_cover_fraction(n_values, C) <= log2_p


def candidate_readouts(X, v, codeword, weight_shape):
    """Function-preserving re-readings of the carrier, cheapest first: [(label, moved_channels, carrier vector)].

    The verifier decodes each and accepts only an EXACT match with the signed payload. 'raw' is the model as given.
    Only 'raw' is offered when undo_is_safe() says the search could fit a random codeword."""
    C, K = carrier_blocks(weight_shape)
    V = np.asarray(v, dtype=np.float64).reshape(C, K)
    yield "raw", 0, V.ravel()
    if not undo_is_safe(len(codeword), weight_shape):
        return
    perm, moved = align_permutation(X, V.ravel(), codeword, weight_shape)
    if moved:
        yield "permutation", moved, apply_permutation(V.ravel(), perm, weight_shape)
    scaled, _ = recover_scales(X, V.ravel(), codeword, weight_shape)
    if scaled is not None:
        yield "scaling", 0, scaled
    unit = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-12)   # order matching that ignores scale
    perm_u, moved_u = align_permutation(X, unit.ravel(), codeword, weight_shape)
    if moved_u:
        scaled_p, _ = recover_scales(X, apply_permutation(V.ravel(), perm_u, weight_shape), codeword, weight_shape)
        if scaled_p is not None:
            yield "permutation + scaling", moved_u, scaled_p


def log2_tail(n, k):
    """log2 P(Binomial(n, 1/2) >= k), exact (no scipy needed, works far below float underflow)."""
    if k <= 0:
        return 0.0
    if k > n:
        return float("-inf")
    terms = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) for i in range(k, n + 1)]
    m = max(terms)
    return (m + math.log(sum(math.exp(t - m) for t in terms))) / math.log(2) - n


def evidence_threshold(n, log2_p=EVIDENCE_LOG2_P):
    """Smallest number of agreements k with P(Bin(n, 1/2) >= k) <= 2^log2_p."""
    return next(k for k in range(n // 2, n + 1) if log2_tail(n, k) <= log2_p)


def agreement(logits, codeword):
    """How many code values read (score > 0) the way the signed codeword says."""
    bits = (np.asarray(logits, dtype=np.float64) > 0).astype(int)
    return int((bits == np.asarray(codeword, dtype=int)).sum())
