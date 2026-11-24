// /r/:token  The respondent's personal link. One question per screen.
//
// How it works:
//   1. Ask the server for the current screen (it resumes at the first unanswered question).
//   2. The person answers; we check it in the browser for instant feedback.
//   3. "Next" sends the answer. The server saves it at once and replies with the next screen.
//   4. "Back" asks the server for the previous question, with the saved answer filled in.
import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CheckCircle2, CloudOff, Loader2 } from "lucide-react";
import { Button, ErrorBox, ProgressBar, Skeleton, cx } from "../components/ui";
import { ApiError, api } from "../lib/api";
import type { AnswerDraft, QuestionScreen, Screen } from "../lib/types";
import { EndView } from "./EndView";
import { QuestionInput } from "./inputs";
import { Brand, RespondentShell } from "./Shell";
import { checkAnswer, emptyValue } from "./validate";

type SaveState = "idle" | "saving" | "saved" | "offline";

function startDraft(screen: QuestionScreen): AnswerDraft {
  return screen.answer
    ? { value: screen.answer.value, other_text: screen.answer.other_text }
    : { value: emptyValue(screen.question), other_text: null };
}

export function SurveyPage({ tokenOverride }: { tokenOverride?: string }) {
  const params = useParams();
  const token = tokenOverride ?? params.token ?? "";
  const [screen, setScreen] = useState<Screen | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<AnswerDraft>({ value: null, other_text: null });
  const [error, setError] = useState<string | null>(null);
  const [save, setSave] = useState<SaveState>("idle");
  const [busy, setBusy] = useState<"next" | "back" | null>(null);

  const show = useCallback((next: Screen) => {
    setScreen(next);
    setError(null);
    if (next.kind === "question") setDraft(startDraft(next));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const load = useCallback(() => {
    setLoadError(null);
    api.screen(token).then(show).catch((err: ApiError) => setLoadError(err.message));
  }, [token, show]);

  useEffect(load, [load]);

  // "Saved" fades back to nothing after a moment.
  useEffect(() => {
    if (save !== "saved") return;
    const timer = setTimeout(() => setSave("idle"), 1800);
    return () => clearTimeout(timer);
  }, [save]);

  async function next() {
    if (!screen || screen.kind !== "question" || busy) return;
    const problem = checkAnswer(screen.question, draft);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy("next");
    setSave("saving");
    try {
      const value = screen.question.type === "info" ? null : draft.value;
      const reply = await api.answer(token, screen.question.qid, value, draft.other_text);
      setSave("saved");
      show(reply);
    } catch (err) {
      const e = err as ApiError;
      setSave(e.status === 0 ? "offline" : "idle");
      if (e.status === 409) load(); // the survey moved on (e.g. closed): show the fresh state
      else setError(e.status === 0 ? "Couldn't save: you seem to be offline. Your answer is still here; tap Next to try again." : e.message);
    } finally {
      setBusy(null);
    }
  }

  async function back() {
    if (!screen || screen.kind !== "question" || !screen.previous_qid || busy) return;
    setBusy("back");
    try {
      show(await api.question(token, screen.previous_qid));
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  // ---- first load
  if (loadError) {
    return (
      <RespondentShell header={<Header />}>
        <div className="my-auto"><ErrorBox title="We couldn't open this survey" message={loadError} onRetry={load} /></div>
      </RespondentShell>
    );
  }
  if (!screen) {
    return (
      <RespondentShell header={<Header />}>
        <div className="space-y-4 pt-6" aria-label="Loading">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-7 w-4/5" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      </RespondentShell>
    );
  }

  // ---- end screens
  if (screen.kind === "end") {
    return (
      <RespondentShell testRun={screen.is_test} header={<Header title={screen.survey_title} progress={screen.progress ?? undefined} />}>
        <EndView screen={screen} />
      </RespondentShell>
    );
  }

  // ---- a question
  const q = screen.question;
  const isInfo = q.type === "info";
  return (
    <RespondentShell
      testRun={screen.is_test}
      header={<Header title={screen.survey_title} progress={screen.progress} save={save} />}
      footer={
        <div className="flex items-center gap-3">
          {screen.previous_qid && (
            <Button variant="secondary" size="lg" onClick={back} loading={busy === "back"} disabled={busy === "next"}
              icon={<ArrowLeft className="size-5" />} aria-label="Back" className="px-4">
              <span className="hidden sm:inline">Back</span>
            </Button>
          )}
          <Button size="lg" className="flex-1" onClick={next} loading={busy === "next"} disabled={busy === "back"}>
            {isInfo ? "Continue" : "Next"} {busy !== "next" && <ArrowRight className="size-5" />}
          </Button>
        </div>
      }
    >
      <form
        key={q.qid}
        className="animate-enter"
        onSubmit={(e) => { e.preventDefault(); next(); }}
      >
        <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-600">
          {isInfo ? "Information" : q.required ? "Required" : "Optional"}
        </div>
        <h1 className={cx("font-semibold leading-snug tracking-tight text-slate-900", isInfo ? "text-xl" : "text-[22px]")}>
          {q.text}
        </h1>
        <div className="mt-6">
          <QuestionInput
            question={q}
            draft={draft}
            onChange={(d) => { setDraft(d); setError(null); }}
            onSubmit={next}
            disabled={busy !== null}
          />
        </div>
        {error && (
          <p role="alert" className="mt-4 flex animate-enter items-start gap-2 rounded-xl bg-rose-50 px-3.5 py-3 text-sm font-medium text-rose-700 ring-1 ring-rose-200">
            {save === "offline" && <CloudOff className="mt-0.5 size-4 shrink-0" />}
            {error}
          </p>
        )}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </RespondentShell>
  );
}

function Header({ title, progress, save = "idle" }: { title?: string; progress?: number; save?: SaveState }) {
  return (
    <header className="px-5 pt-5 sm:px-8 sm:pt-7">
      <div className="flex h-6 items-center justify-between gap-3">
        <Brand />
        <span className="flex items-center gap-1.5 text-xs font-medium" aria-live="polite">
          {save === "saving" && <><Loader2 className="size-3.5 animate-spin text-slate-400" /><span className="text-slate-500">Saving…</span></>}
          {save === "saved" && <><CheckCircle2 className="size-3.5 text-emerald-500" /><span className="text-emerald-700">Saved</span></>}
          {save === "offline" && <><CloudOff className="size-3.5 text-rose-500" /><span className="text-rose-600">Not saved</span></>}
        </span>
      </div>
      {title && <p className="mt-4 truncate text-sm text-slate-500">{title}</p>}
      {progress !== undefined && (
        <div className="mt-2 flex items-center gap-3">
          <ProgressBar value={progress} label="Progress" className="flex-1" />
          <span className="w-9 text-right text-xs font-semibold tabular-nums text-slate-500">{progress}%</span>
        </div>
      )}
    </header>
  );
}
