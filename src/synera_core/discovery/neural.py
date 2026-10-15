"""Neural Interaction Detection (a corroborating second opinion, never a sole basis for a call).

A small seeded PyTorch MLP (CPU, two hidden layers, early stopping on a contiguous hold-out block)
is fitted to the outcome. Following Tsang et al. (2018), the interaction strength of a feature pair
is read from the first-layer weights: for hidden unit ``k`` with influence ``s_k`` (the magnitude of
its path to the output), the pair contributes ``s_k * min(|W1[k,i]|, |W1[k,j]|)``.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def run_neural_interactions(X: pd.DataFrame, y: np.ndarray, stressors: Sequence[str] | None = None,
                            seed: int = 0, hidden: tuple[int, int] = (32, 16), max_epochs: int = 150,
                            patience: int = 12) -> dict:
    """Pairwise NID strengths over ``stressors`` (nuisance columns are fitted but not reported)."""
    import torch
    import torch.nn as nn

    prev_threads = torch.get_num_threads()
    torch.set_num_threads(1)   # single-threaded CPU training is bit-for-bit repeatable (needed for the replay check)
    cols = list(X.columns)
    stressors = list(stressors) if stressors is not None else cols
    order = stressors + [c for c in cols if c not in stressors]
    Xv = X[order].to_numpy(np.float32)
    yv = np.asarray(y, np.float32)
    mu, sd = Xv.mean(0), Xv.std(0) + 1e-6
    Xs = (Xv - mu) / sd
    ym, ys = float(yv.mean()), float(yv.std() + 1e-6)
    ysd = (yv - ym) / ys

    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    n = len(Xs)
    cut = int(n * 0.8)
    Xt, yt = torch.tensor(Xs), torch.tensor(ysd)
    net = nn.Sequential(nn.Linear(Xs.shape[1], hidden[0]), nn.ReLU(),
                        nn.Linear(hidden[0], hidden[1]), nn.ReLU(), nn.Linear(hidden[1], 1))
    opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=1e-3)
    loss_fn = nn.MSELoss()
    best, best_state, bad = float("inf"), None, 0
    for _ in range(max_epochs):
        net.train()
        perm = torch.randperm(cut, generator=gen)
        for s in range(0, cut, 128):
            b = perm[s:s + 128]
            opt.zero_grad()
            loss_fn(net(Xt[b]).squeeze(-1), yt[b]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            val = float(loss_fn(net(Xt[cut:]).squeeze(-1), yt[cut:]))
        if val < best - 1e-5:
            best, bad = val, 0
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        net.load_state_dict(best_state)

    with torch.no_grad():
        pred = net(Xt[cut:]).squeeze(-1).numpy()
    r2 = 1.0 - float(np.sum((ysd[cut:] - pred) ** 2) / (np.sum((ysd[cut:] - ysd[cut:].mean()) ** 2) + 1e-12))

    W1 = net[0].weight.detach().abs().numpy()           # (h1, p)
    W2 = net[2].weight.detach().abs().numpy()           # (h2, h1)
    w_out = net[4].weight.detach().abs().numpy()        # (1, h2)
    s = (w_out @ W2).ravel()                            # influence of each first-layer unit
    k = len(stressors)
    mat = np.zeros((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            mat[i, j] = mat[j, i] = float(np.sum(s * np.minimum(W1[:, i], W1[:, j])))

    pairs = [{"a": stressors[i], "b": stressors[j], "strength": float(mat[i, j])}
             for i in range(k) for j in range(i + 1, k)]
    pairs.sort(key=lambda d: -d["strength"])
    for r, d in enumerate(pairs, 1):
        d["rank"] = r
    torch.set_num_threads(prev_threads)
    return {
        "interaction_matrix": mat, "stressors": stressors, "ranked_pairs": pairs,
        "holdout_r2": float(r2), "corroborating_only": True, "method": "NeuralInteractionDetection",
    }
