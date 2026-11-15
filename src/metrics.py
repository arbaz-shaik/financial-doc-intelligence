"""Custom Prometheus metrics for the AI pipeline.

Defined once here and imported where they are recorded, so every metric
has exactly one definition (defining the same metric twice raises an error).
"""

from prometheus_client import Counter, Enum, Histogram

# Counter with a low-cardinality label: route is one of a small fixed set
QUERIES = Counter(
    "findoc_queries",
    "Questions answered by /ask, by agent route",
    ["route"],
)

# Histogram with buckets sized for LLM calls (seconds), not fast web requests
LLM_CALL_SECONDS = Histogram(
    "findoc_llm_call_seconds",
    "Duration of each Groq LLM call",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 20, 30, 60),
)

LLM_FAILURES = Counter(
    "findoc_llm_failures",
    "Groq LLM calls that raised an error",
)

# Enum = the "state" gauge pattern: exactly one state is 1, the others 0
INDEX_STATUS = Enum(
    "findoc_index_status",
    "State of the vector index built at startup",
    states=["building", "ready", "failed"],
)