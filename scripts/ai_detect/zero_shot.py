"""Binoculars statistics (Hans et al., ICML 2024) from an observer/performer pair of causal LMs.

No training data is needed. Orientation: the Binoculars score is performer log-perplexity divided by
cross-perplexity, so LOWER = more AI-like (the original orientation). Binoculars has no published
evaluation on code, so scores are not comparable to published thresholds, and the Qwen pair differs from
the original Falcon-7B pair.

The pair must share one tokenizer:
  observer  = Qwen/Qwen2.5-Coder-1.5B
  performer = Qwen/Qwen2.5-Coder-1.5B-Instruct
"""
from .device import pick_device, pick_dtype

DEFAULT_OBSERVER = "Qwen/Qwen2.5-Coder-1.5B"
DEFAULT_PERFORMER = "Qwen/Qwen2.5-Coder-1.5B-Instruct"


def _torch():
    import torch
    return torch


class CausalLM:
    """A causal LM plus tokenizer; returns next-token logits for a token-id tensor."""

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

    def logits(self, ids):
        """Logits predicting tokens 1..n-1 and the targets they predict."""
        torch = _torch()
        with torch.no_grad():
            out = self.model(input_ids=ids).logits[0, :-1].float()
        return out, ids[0, 1:]


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
