"""Where evaluation inputs and outputs live. Override with environment variables:

EVAL_GOLDEN   which question set to use (default: the golden set)
EVAL_RUN_DIR  which run folder to read/write (default: evaluation/results)
"""

import os
from pathlib import Path

GOLDEN_FILE = Path(os.environ.get("EVAL_GOLDEN", "evaluation/golden_set.jsonl"))
RUN_DIR = Path(os.environ.get("EVAL_RUN_DIR", "evaluation/results"))
