"""Graph state: the minimum each node needs to do its job and pick the next step.

Deliberately NOT included:
- conversation history: every SDR question is answered on its own from the knowledge base;
  no node reads earlier turns, so carrying them would only grow the state and the checkpoints;
- embeddings or similarity scores: retrieve() already applies the min_score threshold and
  returns plain payloads, and scores must never reach the client.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):
    question: str                    # normalised SDR question
    context: list[dict] | None       # payloads from retrieve() (None until it runs)
    answer: str | None               # final answer for the SDR
    error: str | None                # machine-readable failure code, e.g. "retrieval_failed"
    # Each node appends one entry; the reducer concatenates instead of overwriting, so the
    # final state holds the full ordered list of what ran and what it produced.
    trace_steps: Annotated[list[dict], operator.add]
