"""DroidDetect, the pre-trained supervised code detector we adopt (no training here).

DroidDetect (Orel et al., EMNLP 2025) is the strongest openly released code detector we
found: a ModernBERT encoder trained on DroidCollection (over 1M samples, 43 generators,
7 languages incl. Python, JavaScript, Java, C#), reporting weighted F1 of about 0.95-0.97
(binary) across domains and 0.92 recall on adversarially "humanised" code. Weights are
Apache-2.0 on Hugging Face (project-droid/DroidDetect-Base, -Large, -*-Binary, -*-Ternary).

score() returns P(AI) for each text; predict_logits() the raw class logits: higher = more likely AI-generated.
"""
import numpy as np

from .device import pick_device

DROID_LABELS = {0: "HUMAN_GENERATED", 1: "MACHINE_GENERATED", 2: "MACHINE_REFINED",
                3: "MACHINE_GENERATED_ADVERSARIAL"}


def _torch():
    import torch
    return torch


class DroidDetect:
    """Wrapper for the released DroidDetect checkpoints.

    The checkpoint is a state dict for the TLModel head in the model card: mean-pooled
    encoder states -> Linear(768 or 1024 -> 128) -> ReLU -> Linear(128 -> classes).
    The number of classes is read from the weights, so the binary, ternary and four-class
    releases all load. P(AI) = 1 - P(HUMAN_GENERATED).
    """

    def __init__(self, repo="project-droid/DroidDetect-Base", base=None, device=None, max_tokens=512):
        torch = _torch()
        from huggingface_hub import hf_hub_download
        from transformers import AutoConfig, AutoModel, AutoTokenizer

        base = base or ("answerdotai/ModernBERT-large" if "Large" in repo else "answerdotai/ModernBERT-base")
        self.device = pick_device(torch, device)
        self.tok = AutoTokenizer.from_pretrained(repo)
        state = torch.load(hf_hub_download(repo, "pytorch_model.bin"), map_location="cpu",
                           weights_only=True)
        enc_state = {k[len("text_encoder."):]: v for k, v in state.items() if k.startswith("text_encoder.")}
        # architecture from the base model's config only; the weights are DroidDetect's own
        self.encoder = AutoModel.from_config(AutoConfig.from_pretrained(base))
        missing, unexpected = self.encoder.load_state_dict(enc_state, strict=False)
        if len(missing) > 5:
            raise RuntimeError(f"encoder weights did not load ({len(missing)} missing keys)")
        hidden = state["text_projection.weight"].shape[1]
        proj = state["text_projection.weight"].shape[0]
        self.n_classes = state["classifier.weight"].shape[0]
        self.proj = torch.nn.Linear(hidden, proj)
        self.cls = torch.nn.Linear(proj, self.n_classes)
        self.proj.load_state_dict({"weight": state["text_projection.weight"], "bias": state["text_projection.bias"]})
        self.cls.load_state_dict({"weight": state["classifier.weight"], "bias": state["classifier.bias"]})
        for m in (self.encoder, self.proj, self.cls):
            m.to(self.device).eval()
        self.max_tokens = max_tokens

    def predict_proba(self, texts, batch_size=16):
        torch = _torch()
        out = []
        for i in range(0, len(texts), batch_size):
            enc = self.tok(list(texts[i:i + batch_size]), return_tensors="pt", padding=True,
                           truncation=True, max_length=self.max_tokens).to(self.device)
            with torch.no_grad():
                h = self.encoder(**enc).last_hidden_state
                # the model card mean-pools over all positions (padding included); padding
                # within a batch would change scores, so we pool over real tokens only and
                # recommend batch_size=1 when reproducing published numbers exactly
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (h * mask).sum(1) / mask.sum(1)
                probs = torch.softmax(self.cls(torch.relu(self.proj(pooled))), -1)
            out.append(probs.cpu().numpy())
        return np.vstack(out)

    def score(self, texts, batch_size=16):
        return 1.0 - self.predict_proba(texts, batch_size)[:, 0]

    def predict_logits(self, texts, batch_size=1):
        """Raw class logits (n, n_classes) and the number of real tokens per text (specials included).

        batch_size=1 keeps mean-pooling free of padding, as in the model card."""
        torch = _torch()
        logits, counts = [], []
        for i in range(0, len(texts), batch_size):
            enc = self.tok(list(texts[i:i + batch_size]), return_tensors="pt", padding=True,
                           truncation=True, max_length=self.max_tokens).to(self.device)
            with torch.no_grad():
                h = self.encoder(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (h * mask).sum(1) / mask.sum(1)
                out = self.cls(torch.relu(self.proj(pooled)))
            logits.append(out.float().cpu().numpy())
            counts += [int(n) for n in enc["attention_mask"].sum(1)]
        return np.vstack(logits), counts
