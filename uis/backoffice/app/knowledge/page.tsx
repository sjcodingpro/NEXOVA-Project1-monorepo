"use client";

import { FormEvent, useState } from "react";
import { askSalesAssistant } from "@/lib/knowledge-api";

// Real prospect questions from Marcos Ibáñez's brief (company-BRIEFING.md, section 7).
const EXAMPLES = [
  "How much does an 8-week training program cost?",
  "What happens if the shortlist doesn't work for me?",
  "How long does a typical headhunting process take?",
];

type State =
  | { kind: "idle" }
  | { kind: "loading"; question: string }
  | { kind: "answered"; question: string; answer: string }
  | { kind: "error"; question: string; message: string };

export default function SalesAssistantPage() {
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const loading = state.kind === "loading";

  async function ask(q: string) {
    const trimmed = q.trim();
    if (trimmed.length < 3 || loading) return;
    setState({ kind: "loading", question: trimmed });
    try {
      const { answer } = await askSalesAssistant(trimmed);
      if (!answer?.trim()) throw new Error("The assistant returned an empty answer.");
      setState({ kind: "answered", question: trimmed, answer });
    } catch (err: unknown) {
      setState({
        kind: "error",
        question: trimmed,
        message: err instanceof Error ? err.message : "The sales assistant couldn't be reached.",
      });
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold">Sales Assistant</h1>
      <p className="text-slate-400 text-sm mt-2 max-w-xl">
        Ask what a prospect just asked you. Answers come only from Nexova&apos;s service lines,
        pricing model, hiring-process SLA and objection-handling guides.
      </p>

      <form onSubmit={onSubmit} className="mt-6">
        <label htmlFor="question" className="block text-xs uppercase tracking-wide text-slate-400 mb-2">
          Prospect question
        </label>
        <textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void ask(question);
            }
          }}
          rows={3}
          maxLength={1000}
          placeholder="e.g. Can you go below your 22% fee?"
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading || question.trim().length < 3}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Thinking…" : "Ask"}
          </button>
          {loading && <span className="text-xs text-slate-400" role="status">Searching the knowledge base…</span>}
        </div>
      </form>

      <div className="mt-4 flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            disabled={loading}
            onClick={() => {
              setQuestion(example);
              void ask(example);
            }}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-slate-500 hover:text-white disabled:opacity-50"
          >
            {example}
          </button>
        ))}
      </div>

      {state.kind === "answered" && (
        <section className="mt-8 rounded-lg border border-slate-800 bg-slate-900/50 px-5 py-4" aria-live="polite">
          <p className="text-xs uppercase tracking-wide text-slate-500">You asked</p>
          <p className="mt-1 text-sm text-slate-300">{state.question}</p>
          <p className="mt-4 text-xs uppercase tracking-wide text-slate-500">Suggested answer</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{state.answer}</p>
        </section>
      )}

      {state.kind === "error" && (
        <section className="mt-8 rounded-lg border border-red-900 bg-red-950/40 px-5 py-4" role="alert">
          <p className="text-sm font-medium text-red-300">No answer — the request failed</p>
          <p className="mt-1 text-sm text-red-200/80">{state.message}</p>
          <button
            type="button"
            onClick={() => void ask(state.question)}
            className="mt-3 text-xs text-red-200 underline hover:text-white"
          >
            Try again
          </button>
        </section>
      )}
    </div>
  );
}
