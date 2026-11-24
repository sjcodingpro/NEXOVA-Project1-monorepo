"""Graph nodes. One responsibility each; RAG logic is imported from data/pipelines/rag.py,
never re-implemented here.

- receive_question  normalise and validate the question
- route_intent      decide: knowledge base (rag), live ticket data (ticket_tool), or both
- lookup_ticket     services.agent.tools.lookup_ticket (incident manager, read-only, 4s timeout)
- handle_tool_failure  honest text when the ticket tool times out, errors or finds nothing
- synthesize_answer    merge ticket facts (verbatim from the tool) with a RAG answer
- retrieve          data.pipelines.rag.retrieve(question)           (search only)
- generate          data.pipelines.rag.generate_answer(question, context)  (generation only)
- no_context        honest fixed answer when nothing cleared min_score (no model call,
                    so it cannot invent Nexova facts)

The monolithic rag.query() (retrieve + generate) is deliberately never called: retrieval
runs exactly once, in its own node, and generation reuses its output.
"""
from __future__ import annotations

import re

from data.pipelines import rag as rag_pipeline
from services.agent import tools
from services.agent.tracing import traced

MAX_QUESTION_CHARS = 1000

NO_CONTEXT_ANSWER = (
    "I don't have information about that in Nexova's sales knowledge base. "
    "Please check with a senior account manager before answering the prospect."
)


@traced("receive_question")
def receive_question(state: dict):
    question = re.sub(r"\s+", " ", state.get("question") or "").strip()
    if not question:
        return ({"question": "", "error": "empty_question"},
                "rejected: the question is empty", {"error": "empty_question"})
    if len(question) > MAX_QUESTION_CHARS:
        return ({"question": question[:MAX_QUESTION_CHARS], "error": "question_too_long"},
                f"rejected: {len(question)} characters (max {MAX_QUESTION_CHARS})",
                {"error": "question_too_long"})
    return ({"question": question, "error": None},
            f"accepted ({len(question)} characters)", {"question": question})


@traced("retrieve")
def retrieve_node(state: dict):
    try:
        context = rag_pipeline.retrieve(state.get("rag_question") or state["question"])
    except Exception as exc:  # Qdrant down, embeddings API error...
        return ({"context": None, "error": "retrieval_failed"},
                f"failed: {type(exc).__name__}", {"error": "retrieval_failed"})
    chunks = [{"source_document": c.get("source_document"), "section": c.get("section"),
               "chunk_index": c.get("chunk_index"), "text": c.get("text")} for c in context]
    searched = state.get("rag_question") or state["question"]
    return ({"context": context},
            f"{len(context)} chunk(s) above min_score {rag_pipeline.DEFAULT_MIN_SCORE}",
            {"searched": searched, "chunks": chunks})


@traced("generate")
def generate_node(state: dict):
    try:
        answer = rag_pipeline.generate_answer(state["question"], state["context"])
    except Exception as exc:  # model API error, timeout...
        return ({"answer": None, "error": "generation_failed"},
                f"failed: {type(exc).__name__}", {"error": "generation_failed"})
    if not answer:
        return ({"answer": None, "error": "generation_failed"},
                "failed: empty answer from the model", {"error": "generation_failed"})
    return ({"answer": answer}, f"answered from {len(state['context'])} chunk(s)",
            {"answer": answer})


@traced("no_context")
def no_context_node(state: dict):
    return ({"answer": NO_CONTEXT_ANSWER},
            "no chunk cleared min_score: honest 'not covered' answer, model not called",
            {"answer": NO_CONTEXT_ANSWER})


# ------------------------------------------------------------------ Part 2: intent routing
_TICKET_WORDS = re.compile(r"\b(tickets?|incidents?|cases?)\b", re.I)
_TICKET_ID = re.compile(r"(?:\b(?:tickets?|incidents?|cases?)\s*(?:#|no\.?|number|id)?\s*#?|#)(\d{1,7})\b", re.I)
_STATUS_WORDS = [
    (re.compile(r"\bin[\s-]?progress\b", re.I), "in_progress"),
    (re.compile(r"\b(resolved|closed)\b", re.I), "resolved"),
    (re.compile(r"\bdiscarded\b", re.I), "discarded"),
    (re.compile(r"\bopen\b", re.I), "open"),
]
# Topics only the knowledge base (service lines, pricing, SLA, objections) can answer.
_POLICY_WORDS = re.compile(
    r"\b(fees?|pric(e|es|ing)|costs?|discounts?|guarantees?|replacement|shortlists?|sla|"
    r"training|programs?|programmes?|outsourc\w*|contracts?|cancel\w*|installments?|payments?|"
    r"pay|competitors?|polic(y|ies)|refunds?|service lines?|headhunting)\b|%", re.I)


def _policy_part(question: str) -> str:
    """For a mixed question, the clause(s) that carry the policy topic, without the ticket
    reference: "Ticket 96 came from a client: what does our replacement guarantee cover?"
    -> "what does our replacement guarantee cover?". Searching with the ticket wording would
    dilute the similarity and drop the right chunk below min_score."""
    clauses = [c.strip() for c in re.split(r"(?<=[:;?!.])\s+|\s+[-–—]\s+|,\s+(?=(?:and|but|also|what|how|can|do|does|is)\b)", question) if c.strip()]
    policy = [c for c in clauses if _POLICY_WORDS.search(c) and not _TICKET_ID.search(c)]
    if policy:
        return " ".join(policy)
    return re.sub(r"\s{2,}", " ", _TICKET_ID.sub("", question)).strip()


@traced("route_intent")
def route_intent(state: dict):
    """Pick the source(s) from the question itself; the user never names one.

    ticket_tool  the question refers to a ticket/incident (by number, or by status for a list)
    rag          anything else: Nexova's services, pricing, SLA, objections
    both         a ticket reference AND a policy topic in the same question
    """
    q = state["question"]
    ticket_id = _TICKET_ID.search(q)
    mentions_ticket = bool(ticket_id or _TICKET_WORDS.search(q))
    policy = _POLICY_WORDS.search(q)

    if not mentions_ticket:
        route, why, query = "rag", "no ticket or incident reference: knowledge-base question", None
    else:
        if ticket_id:
            query = {"ticket_id": int(ticket_id.group(1))}
            found = f"ticket #{ticket_id.group(1)}"
        else:
            status = next((value for rx, value in _STATUS_WORDS if rx.search(q)), None)
            query = {"status": status} if status else {}
            found = f"tickets with status '{status}'" if status else "a ticket without a number"
        if policy:
            route, why = "both", f"asks about {found} and a policy topic ('{policy.group(0)}')"
        else:
            route, why = "ticket_tool", f"asks about {found}: live incident-manager data"
    rag_question = q if route == "rag" else (_policy_part(q) if route == "both" else None)
    return ({"route": route, "route_rationale": why, "ticket_query": query, "rag_question": rag_question},
            f"route={route}: {why}",
            {"route": route, "rationale": why, "ticket_query": query, "rag_question": rag_question})


@traced("lookup_ticket")
def lookup_ticket_node(state: dict):
    query = tools.TicketLookupInput(**(state.get("ticket_query") or {}))
    result = tools.lookup_ticket(query)
    summary = (f"{result.outcome}: {len(result.tickets)} ticket(s)" if result.found
               else f"{result.outcome}: {result.error}")
    data = result.model_dump()
    return ({"tool_result": data}, summary, data)


@traced("handle_tool_failure")
def handle_tool_failure(state: dict):
    """Map a failed lookup to an honest sentence. Never states a status the tool didn't return."""
    result = state.get("tool_result") or {}
    query = result.get("query") or {}
    outcome = result.get("outcome")
    if outcome == "not_found" and query.get("ticket_id"):
        text = (f"I couldn't find ticket #{query['ticket_id']} in the incident manager. "
                "Please double-check the ticket number.")
    elif outcome == "not_found" and query.get("status"):
        text = f"There are no tickets with status \"{tools.STATUS_LABELS[query['status']]}\" in the incident manager right now."
    elif outcome == "error" and not query.get("ticket_id") and not query.get("status"):
        text = "Which ticket do you mean? Give me the ticket number and I'll check its status in the incident manager."
    else:  # timeout or service error
        text = ("I couldn't confirm that ticket's status right now: the incident manager didn't respond. "
                "Please try again in a moment or check the incident manager directly.")
    return ({"tool_fallback": text}, f"fallback for outcome={outcome}", {"answer_text": text})


def _day(iso: str) -> str:
    return (iso or "")[:10]


def _ticket_text(result: dict) -> str:
    tickets = result["tickets"]
    if result["query"].get("ticket_id") is not None:
        t = tickets[0]
        return (f"Ticket #{t['ticket_id']} \"{t['title']}\" is **{tools.STATUS_LABELS.get(t['status'], t['status'])}**. "
                f"Category: {tools.CATEGORY_LABELS.get(t['category'], t['category'])}; "
                f"origin: {tools.ORIGIN_LABELS.get(t['origin'], t['origin'])}; "
                f"branch: {tools.BRANCH_LABELS.get(t['branch'], t['branch'])}. "
                f"Opened {_day(t['created_at'])}, last updated {_day(t['updated_at'])}.")
    label = tools.STATUS_LABELS.get(result["query"].get("status"), "")
    listed = "; ".join(f"#{t['ticket_id']} \"{t['title']}\" ({tools.CATEGORY_LABELS.get(t['category'], t['category'])}, "
                       f"opened {_day(t['created_at'])})" for t in tickets)
    n = result["total_matching"]
    verb, noun = ("is", "ticket") if n == 1 else ("are", "tickets")
    return (f"There {verb} {n} {noun} with status \"{label}\" in the incident manager. "
            f"Most recent: {listed}.")


@traced("synthesize_answer")
def synthesize_answer(state: dict):
    """Final answer for ticket_tool / both routes. Ticket facts are copied from the tool's
    output (no model involved, so a status can't be invented); the policy part, if any,
    comes from generate_answer() on the retrieved context."""
    result = state.get("tool_result") or {}
    parts = [state["tool_fallback"]] if state.get("tool_fallback") else [_ticket_text(result)]
    sources = ["incident manager (live)"] if result.get("found") else []
    used_rag = False
    if state.get("route") == "both":
        if state.get("error") == "retrieval_failed":
            parts.append("I couldn't reach the knowledge base for the policy part of your question right now.")
        elif state.get("context"):
            parts.append(rag_pipeline.generate_answer(state.get("rag_question") or state["question"],
                                                      state["context"]))
            used_rag = True
        else:
            parts.append("The knowledge base has no policy information for the rest of your question; "
                         "please check with a senior account manager.")
    answer = "\n\n".join(parts)
    if sources:
        answer += "\n\nSource: " + ", ".join(sources)
    return ({"answer": answer, "error": None},   # ticket answer survives a knowledge-base outage
            f"merged {'ticket data' if result.get('found') else 'tool fallback'}"
            f"{' + knowledge-base answer' if used_rag else ''}",
            {"answer": answer})


# --------------------------------------------------------------------------- routing
def route_after_receive(state: dict) -> str:
    return "end" if state.get("error") else "route_intent"


def route_after_intent(state: dict) -> str:
    return "retrieve" if state.get("route") == "rag" else "lookup_ticket"


def route_after_lookup(state: dict) -> str:
    if not (state.get("tool_result") or {}).get("found"):
        return "handle_tool_failure"
    return "retrieve" if state.get("route") == "both" else "synthesize_answer"


def route_after_tool_failure(state: dict) -> str:
    return "retrieve" if state.get("route") == "both" else "synthesize_answer"


def route_after_retrieve(state: dict) -> str:
    if state.get("route") == "both":
        return "synthesize_answer"   # the ticket part is still worth answering
    if state.get("error"):
        return "end"
    return "generate" if state.get("context") else "no_context"
