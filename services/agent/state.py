"""Graph state: the minimum each node needs to do its job and pick the next step.

Deliberately NOT included:
- conversation history: every question is answered on its own; no node reads earlier turns,
  so carrying them would only grow the state and the checkpoints;
- embeddings or similarity scores: retrieve() already applies the min_score threshold and
  returns plain payloads, and scores must never reach the client.

Part 2 adds only what routing and the ticket tool need: the router's decision (route,
rationale, the ticket id or status it extracted), the tool's typed result, and the honest
fallback text when the tool fails.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

Route = Literal["rag", "ticket_tool", "both"]


class AgentState(TypedDict, total=False):
    question: str                    # normalised question
    route: Route | None              # set by route_intent
    route_rationale: str | None      # why route_intent chose it (shown in the trace)
    ticket_query: dict | None        # TicketLookupInput as a dict: {"ticket_id"} or {"status"}
    rag_question: str | None         # what retrieve() searches: the question minus its ticket part (route "both")
    tool_result: dict | None         # TicketLookupOutput as a dict
    tool_fallback: str | None        # honest text when the ticket tool failed
    context: list[dict] | None       # payloads from retrieve() (None until it runs)
    answer: str | None               # final answer
    error: str | None                # machine-readable failure code, e.g. "retrieval_failed"
    # Each node appends one entry; the reducer concatenates instead of overwriting, so the
    # final state holds the full ordered list of what ran and what it produced.
    trace_steps: Annotated[list[dict], operator.add]
