"""Zero-shot detectors built on a causal code language model.

No training data is needed; each detector turns the model's token probabilities into one
score, oriented so that HIGHER = MORE LIKELY AI-GENERATED. Implemented:

  loglik         mean token log-likelihood (Gehrmann et al. 2019; GLTR family)
  logrank        minus mean log-rank of the observed tokens (Solaiman et al. 2019)
  entropy        minus mean predictive entropy
  fast_detectgpt analytic conditional-probability curvature (Bao et al., ICLR 2024)
  binoculars     minus (log-perplexity / cross-perplexity) of two related models
                 (Hans et al., ICML 2024); needs an observer/performer pair with one tokenizer
  detectcodegpt  normalised perturbed log-rank with whitespace/newline perturbations
                 (Shi et al., 2024), the zero-shot method designed for code

Published accuracy (see docs/ai_detection.md): DetectCodeGPT mean AUROC 0.83 over 24
Python settings vs 0.77 for log-rank; Fast-DetectGPT averaged 0.68 weighted F1 on the
DroidCollection domain split; Binoculars has no published code evaluation. All of them
lose accuracy at high sampling temperature, so thresholds must be set on in-domain data.

Recommended models (open weights, same tokenizer for the Binoculars pair):
  observer  = Qwen/Qwen2.5-Coder-1.5B
  performer = Qwen/Qwen2.5-Coder-1.5B-Instruct
"""
import math

import numpy as np

from .device import pick_device, pick_dtype

DEFAULT_OBSERVER = "Qwen/Qwen2.5-Coder-1.5B"
DEFAULT_PERFORMER = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


def _torch():
    import torch
    return torch


class CausalLM:
    """A causal LM plus tokenizer; returns next-token logits for a text."""

    def __init__(self, model=None, tokenizer=None, name=None, device=None, max_tokens=512,
                 dtype=None):
        torch = _torch()
        self.device = pick_device(torch, device)
        if model is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(name)
            model = AutoModelForCausalLM.from_pretrained(
                name, dtype=dtype or pick_dtype(torch, self.device))
        self.model = model.to(self.device).eval()
        self.tok = tokenizer
        self.max_tokens = max_tokens
        self.name = name or type(model).__name__

    def encode(self, text):
        enc = self.tok(text, return_tensors="pt", truncation=True, max_length=self.max_tokens)
        return enc["input_ids"].to(self.device)

    def logits(self, ids):
        """Logits predicting tokens 1..n-1 and the targets they predict."""
        torch = _torch()
        with torch.no_grad():
            out = self.model(input_ids=ids).logits[0, :-1].float()
        return out, ids[0, 1:]


def token_stats(logits, targets):
    """Per-token log-prob, log-rank and entropy from one forward pass."""
    torch = _torch()
    logp = torch.log_softmax(logits, -1)
    ll = logp.gather(-1, targets[:, None]).squeeze(-1)
    rank = (logp > ll[:, None]).sum(-1) + 1
    ent = -(logp.exp() * logp).sum(-1)
    return ll, torch.log(rank.float()), ent


def fast_detectgpt_score(score_logits, ref_logits, targets):
    """Analytic sampling discrepancy (Bao et al. 2024, Eq. 6 with the analytic mean/var)."""
    torch = _torch()
    lp_s = torch.log_softmax(score_logits, -1)
    p_r = torch.softmax(ref_logits, -1)
    ll = lp_s.gather(-1, targets[:, None]).squeeze(-1)
    mean = (p_r * lp_s).sum(-1)
    var = (p_r * lp_s.pow(2)).sum(-1) - mean.pow(2)
    return float((ll.sum() - mean.sum()) / var.sum().clamp_min(1e-8).sqrt())


def binoculars_score(observer_logits, performer_logits, targets):
    """B = log PPL / log X-PPL as in the reference implementation; returns -B so higher = AI."""
    torch = _torch()
    nll = torch.nn.functional.cross_entropy(performer_logits, targets, reduction="mean")
    x_ent = -(torch.softmax(observer_logits, -1) * torch.log_softmax(performer_logits, -1)).sum(-1).mean()
    return float(-(nll / x_ent.clamp_min(1e-8)))


def binodroid_inputs(observer_logits, performer_logits, targets, ll, log_rank, entropy):
    """The Binoculars-derived inputs of BinoDroid, from the passes already made for the zero-shot scores.

    bd_obs_nll / bd_perf_nll  mean negative log-likelihood under the observer / performer (log-perplexity)
    bd_xent                   cross-perplexity: the observer's next-token distribution scored by the performer
    bd_ratio_perf, bd_ratio_obs  log-perplexity / cross-perplexity (bd_ratio_perf is the Binoculars statistic B)
    bd_entropy                mean predictive entropy of the observer
    bd_ll_std                 standard deviation of the per-token log-probability under the observer
    bd_rank1                  share of tokens that the observer ranks first
    """
    torch = _torch()
    perf_nll = float(torch.nn.functional.cross_entropy(performer_logits, targets, reduction="mean"))
    xent = float(-(torch.softmax(observer_logits, -1) * torch.log_softmax(performer_logits, -1)).sum(-1).mean())
    obs_nll = float(-ll.mean())
    xent = max(xent, 1e-8)
    return {"bd_obs_nll": obs_nll, "bd_perf_nll": perf_nll, "bd_xent": xent,
            "bd_ratio_perf": perf_nll / xent, "bd_ratio_obs": obs_nll / xent,
            "bd_entropy": float(entropy.mean()), "bd_ll_std": float(ll.std()),
            "bd_rank1": float((log_rank == 0).float().mean())}


def perturb_whitespace(text, rng, space_rate=0.5, newline_rate=0.5):
    """DetectCodeGPT perturbation: insert Poisson-many spaces (after existing spaces) or
    blank lines (after existing lines), choosing one kind per perturbation. Extra
    whitespace rarely changes what code does. `rng` is a numpy Generator."""
    lines = text.split("\n")
    if rng.random() < 0.5:
        out = []
        for line in lines:
            parts = line.split(" ")
            ks = rng.poisson(space_rate, max(0, len(parts) - 1))
            out.append(parts[0] + "".join(" " * (1 + int(k)) + p for k, p in zip(ks, parts[1:])))
        return "\n".join(out)
    out = []
    for line, k in zip(lines, rng.poisson(newline_rate, len(lines))):
        out.append(line)
        out.extend([""] * int(k))
    return "\n".join(out)


class ZeroShotSuite:
    """Scores units with every zero-shot detector in one pass per model.

    performer=None skips Binoculars; n_perturb=0 skips DetectCodeGPT (it costs n_perturb
    extra forward passes per unit)."""

    def __init__(self, observer: CausalLM, performer: CausalLM = None, n_perturb=20, seed=0):
        self.obs, self.perf = observer, performer
        self.n_perturb = n_perturb
        self.rng = np.random.default_rng(seed)

    def score(self, text):
        ids = self.obs.encode(text)
        if ids.shape[1] < 8:
            return {}
        lo, tgt = self.obs.logits(ids)
        ll, lr, ent = token_stats(lo, tgt)
        out = {"loglik": float(ll.mean()), "logrank": float(-lr.mean()),
               "entropy": float(-ent.mean())}
        if self.perf is not None:
            lp, _ = self.perf.logits(ids)
            out.update(binodroid_inputs(lo, lp, tgt, ll, lr, ent))
            out["binoculars"] = binoculars_score(lo, lp, tgt)
            # sampling model = observer, scoring model = performer (Bao et al. use a pair too)
            out["fast_detectgpt"] = fast_detectgpt_score(lp, lo, tgt)
        else:
            out["fast_detectgpt"] = fast_detectgpt_score(lo, lo, tgt)
        if self.n_perturb:
            base = float(lr.mean())
            pert = []
            for _ in range(self.n_perturb):
                pids = self.obs.encode(perturb_whitespace(text, self.rng))
                plo, ptgt = self.obs.logits(pids)
                pert.append(float(token_stats(plo, ptgt)[1].mean()))
            # NPR = mean perturbed log-rank / original log-rank; machine code is hurt more
            out["detectcodegpt"] = float(np.mean(pert) / base) if base > 0 else math.nan
        return out


def binoculars_components(observer_logits, performer_logits, targets):
    """Raw Binoculars quantities for one chunk (Hans et al., ICML 2024), all in nats per token.

    obs_logppl   observer log-perplexity (mean NLL of the observed tokens under the observer)
    perf_logppl  performer log-perplexity
    xppl         cross-perplexity: the observer's next-token distribution scored by the performer
    score        perf_logppl / xppl, the Binoculars statistic. LOWER = more AI-like (original orientation).
    """
    torch = _torch()
    ce = torch.nn.functional.cross_entropy
    obs = float(ce(observer_logits, targets, reduction="mean"))
    perf = float(ce(performer_logits, targets, reduction="mean"))
    x = float(-(torch.softmax(observer_logits, -1) * torch.log_softmax(performer_logits, -1)).sum(-1).mean())
    return {"obs_logppl": obs, "perf_logppl": perf, "xppl": x, "score": perf / max(x, 1e-8),
            "n_scored": int(targets.shape[0])}
