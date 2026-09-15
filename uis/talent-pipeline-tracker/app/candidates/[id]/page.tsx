"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Candidate, Note, StatusValue, StageValue } from "@/types/candidate";
import { STATUS_OPTIONS, STAGE_OPTIONS } from "@/lib/labels";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState } from "@/components/ErrorState";

export default function CandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusUpdating, setStatusUpdating] = useState(false);
  const [stageUpdating, setStageUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  // M6: lets the updateError banner's Retry button re-run whichever of
  // status/stage change actually failed, instead of omitting onRetry
  // entirely (there was previously no way to know which of the two
  // in-flight actions to re-attempt).
  const [retryUpdate, setRetryUpdate] = useState<(() => void) | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [noteContent, setNoteContent] = useState("");
  const [addingNote, setAddingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [deletingNoteId, setDeletingNoteId] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [candidateRes, notesRes] = await Promise.all([api.getCandidate(id), api.listNotes(id)]);
      setCandidate(candidateRes);
      setNotes(notesRes.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this candidate.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchAll();
  }, [fetchAll]);

  async function handleStatusChange(value: StatusValue) {
    setStatusUpdating(true);
    setUpdateError(null);
    try {
      await api.patchCandidate(id, { status: value });
      const fresh = await api.getCandidate(id);
      setCandidate(fresh);
      setRetryUpdate(null);
    } catch (err) {
      setUpdateError(err instanceof Error ? err.message : "Could not update status.");
      setRetryUpdate(() => () => handleStatusChange(value));
    } finally {
      setStatusUpdating(false);
    }
  }


  async function handleDeleteCandidate() {
    if (!confirm(`Delete ${candidate?.full_name}? This cannot be undone.`)) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteCandidate(id);
      router.push("/");
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Could not delete candidate.");
      setDeleting(false);
    }
  }
  async function handleStageChange(value: StageValue) {
    setStageUpdating(true);
    setUpdateError(null);
    try {
      await api.patchCandidate(id, { stage: value });
      const fresh = await api.getCandidate(id);
      setCandidate(fresh);
      setRetryUpdate(null);
    } catch (err) {
      setUpdateError(err instanceof Error ? err.message : "Could not update stage.");
      setRetryUpdate(() => () => handleStageChange(value));
    } finally {
      setStageUpdating(false);
    }
  }

  // M6: split out from the form's submit handler so a retry button can
  // call this directly (a retry has no FormEvent to pass through, and
  // didn't need one -- the only thing handleAddNote's event arg was
  // used for was preventDefault).
  async function submitNote() {
    if (!noteContent.trim()) return;
    setAddingNote(true);
    setNoteError(null);
    try {
      await api.addNote(id, { content: noteContent.trim() });
      setNoteContent("");
      const fresh = await api.listNotes(id);
      setNotes(fresh.data);
    } catch (err) {
      setNoteError(err instanceof Error ? err.message : "Could not add note.");
    } finally {
      setAddingNote(false);
    }
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault();
    void submitNote();
  }

  async function handleDeleteNote(noteId: string) {
    setDeletingNoteId(noteId);
    setNoteError(null);
    try {
      await api.deleteNote(id, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch (err) {
      setNoteError(err instanceof Error ? err.message : "Could not delete note.");
    } finally {
      setDeletingNoteId(null);
    }
  }

  if (loading) return <LoadingState label="Loading candidate…" />;
  if (error) return <ErrorState message={error} onRetry={fetchAll} />;
  if (!candidate) {
    // M5: this previously rendered nothing at all -- a completely blank
    // page with no loading state, no error, and no explanation, if the
    // fetch resolved but the record didn't come back (e.g. a stale link
    // to a deleted candidate).
    return (
      <main className="max-w-3xl mx-auto px-4 py-8">
        <p className="text-sm text-gray-500 mb-4">Candidate not found.</p>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Back to pipeline
        </Link>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      <Link href="/" className="text-sm text-blue-600 hover:underline">
        ← Back to pipeline
      </Link>

      <div className="flex items-start justify-between gap-4 mt-4 mb-6">
        <div>
          <h1 className="text-xl font-semibold">{candidate.full_name}</h1>
          <p className="text-sm text-gray-500">{candidate.position}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Link
            href={`/candidates/${candidate.id}/edit`}
            className="border text-sm font-medium px-4 py-2 rounded-md"
          >
            Edit candidate
          </Link>
          <button
            onClick={handleDeleteCandidate}
            disabled={deleting}
            className="border border-red-300 text-red-600 text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Delete candidate"}
          </button>
        </div>
      </div>

      {/* Fields */}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm mb-8 border rounded-md p-4">
        <div>
          <dt className="text-gray-500">Email</dt>
          <dd>{candidate.email}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Phone</dt>
          <dd>{candidate.phone}</dd>
        </div>
        <div>
          <dt className="text-gray-500">LinkedIn</dt>
          <dd>
            {candidate.linkedin_url ? (
              <a
                href={candidate.linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                View profile
              </a>
            ) : (
              <span className="text-gray-400">Not provided</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-gray-500">CV</dt>
          <dd>
              <a
              href={candidate.cv_url}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline"
            >
              View CV
            </a>
          </dd>
        </div>
        <div>
          <dt className="text-gray-500">Years of experience</dt>
          <dd>{candidate.experience_years}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Application date</dt>
          <dd>{new Date(candidate.applied_at).toLocaleDateString()}</dd>
        </div>
      </dl>

      {/* Status / stage controls */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-sm text-gray-500 mb-1">Status</label>
          <select
            value={candidate.status}
            disabled={statusUpdating}
            onChange={(e) => handleStatusChange(e.target.value as StatusValue)}
            className="border rounded-md px-3 py-2 text-sm w-full"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-500 mb-1">Stage</label>
          <select
            value={candidate.stage}
            disabled={stageUpdating}
            onChange={(e) => handleStageChange(e.target.value as StageValue)}
            className="border rounded-md px-3 py-2 text-sm w-full"
          >
            {STAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {/* M6: both banners previously omitted onRetry, so a failed status/
          stage update or a failed delete had no way forward but to
          retry the underlying action manually via the UI controls. */}
      {updateError && (
        <ErrorState message={updateError} onRetry={retryUpdate ?? undefined} />
      )}
      {deleteError && <ErrorState message={deleteError} onRetry={handleDeleteCandidate} />}

      {/* Notes */}
      <div className="mt-8">
        <h2 className="text-sm font-semibold mb-3">Internal notes</h2>

        <form onSubmit={handleAddNote} className="flex gap-2 mb-4">
          <input
            type="text"
            value={noteContent}
            onChange={(e) => setNoteContent(e.target.value)}
            placeholder="Add a note after a call or interview…"
            className="border rounded-md px-3 py-2 text-sm flex-1"
          />
          <button
            type="submit"
            disabled={addingNote || !noteContent.trim()}
            className="bg-black text-white text-sm font-medium px-4 py-2 rounded-md disabled:opacity-50"
          >
            {addingNote ? "Adding…" : "Add"}
          </button>
        </form>
        {/* M6: covers the add-note failure case, which is the common one --
            a delete-note failure can already be retried directly via that
            note's own Delete button, so this only wires the case that
            previously had no path forward at all. */}
        {noteError && (
          <div className="mb-4">
            <ErrorState message={noteError} onRetry={() => void submitNote()} />
          </div>
        )}

        {notes.length === 0 ? (
          <p className="text-sm text-gray-400">No notes yet.</p>
        ) : (
          <ul className="space-y-2">
            {notes.map((note) => (
              <li
                key={note.id}
                className="border rounded-md px-3 py-2 text-sm flex items-start justify-between gap-4"
              >
                <div>
                  <p>{note.content}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(note.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => handleDeleteNote(note.id)}
                  disabled={deletingNoteId === note.id}
                  className="text-red-600 text-xs font-medium shrink-0 disabled:opacity-50"
                >
                  {deletingNoteId === note.id ? "Deleting…" : "Delete"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
