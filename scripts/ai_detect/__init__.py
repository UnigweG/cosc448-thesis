"""Local code-authorship detectors used by scripts/20_file_detect.py.

Modules
  device      pick cuda / mps / cpu and a matching dtype
  zero_shot   Binoculars-style statistics from an observer/performer pair of causal LMs
  supervised  DroidDetect (pre-trained ModernBERT classifier)
  units       file-extension map and the generated-file / test-path patterns
"""
