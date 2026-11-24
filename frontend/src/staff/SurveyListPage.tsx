// /surveys  Every survey at a glance: status, version, completes vs target, deadline.
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, ChevronRight, FilePlus2, FileText, PencilLine } from "lucide-react";
import { Badge, Button, Card, EmptyState, ErrorBox, ProgressBar, Skeleton, StatusChip, cx } from "../components/ui";
import { api } from "../lib/api";
import { CLOSED_LABEL, formatDate, relative } from "../lib/format";
import type { SurveyStatus, SurveySummary } from "../lib/types";
import { PageHeader } from "./StaffLayout";

type Filter = "all" | SurveyStatus;

export function SurveyListPage() {
  const [surveys, setSurveys] = useState<SurveySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const load = useCallback(() => {
    setError(null);
    api.listSurveys().then(setSurveys).catch((err: Error) => setError(err.message));
  }, []);
  useEffect(load, [load]);

  const counts = useMemo(() => {
    const c = { all: 0, draft: 0, live: 0, closed: 0 } as Record<Filter, number>;
    for (const s of surveys ?? []) { c.all++; c[s.status]++; }
    return c;
  }, [surveys]);
  const shown = (surveys ?? []).filter((s) => filter === "all" || s.status === filter);

  return (
    <div>
      <PageHeader
        title="Surveys"
        subtitle="Every questionnaire your team is working on or running."
        actions={<Link to="/surveys/new"><Button icon={<FilePlus2 className="size-4" />}>New survey</Button></Link>}
      />

      {surveys && surveys.length > 0 && (
        <div className="mb-4 flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1 text-sm" role="tablist" aria-label="Filter by status">
          {(["all", "live", "draft", "closed"] as Filter[]).map((f) => (
            <button
              key={f}
              role="tab"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
              className={cx("flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-1.5 font-medium capitalize transition-colors",
                filter === f ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900")}
            >
              {f} <span className="rounded-md bg-slate-200/70 px-1.5 text-xs tabular-nums">{counts[f]}</span>
            </button>
          ))}
        </div>
      )}

      {error && <ErrorBox title="Couldn't load the surveys" message={error} onRetry={load} />}
      {!error && !surveys && (
        <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 w-full rounded-2xl" />)}</div>
      )}
      {surveys && surveys.length === 0 && (
        <EmptyState
          icon={<FileText className="size-6" />}
          title="No surveys yet"
          text="Upload a questionnaire .txt file. It's checked line by line before anything goes live."
          action={<Link to="/surveys/new"><Button icon={<FilePlus2 className="size-4" />}>Upload your first survey</Button></Link>}
        />
      )}
      {surveys && surveys.length > 0 && shown.length === 0 && (
        <p className="rounded-2xl bg-white px-4 py-10 text-center text-sm text-slate-500 ring-1 ring-slate-200">No {filter} surveys.</p>
      )}

      <div className="space-y-3">
        {shown.map((s) => <SurveyRow key={s.id} survey={s} />)}
      </div>
    </div>
  );
}

function SurveyRow({ survey: s }: { survey: SurveySummary }) {
  const pct = s.target ? (100 * s.completed) / s.target : 0;
  return (
    <Link to={`/surveys/${s.id}`} className="block rounded-2xl focus-visible:outline-offset-4">
      <Card className="group p-4 transition-shadow hover:shadow-md sm:p-5">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-base font-semibold text-slate-900 group-hover:text-indigo-700">{s.title}</h2>
              <StatusChip status={s.status} />
              {s.current_version_no ? <Badge>v{s.current_version_no}</Badge> : <Badge tone="amber">Not approved yet</Badge>}
              {s.has_draft && s.current_version_no && <Badge tone="indigo"><PencilLine className="size-3" /> Draft changes</Badge>}
            </div>
            <p className="mt-0.5 font-mono text-xs text-slate-400">{s.slug}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
              {s.current_version_no === null ? (
                <p className="text-xs text-slate-500">{s.has_draft ? "Draft: check, preview, then send for approval" : "No draft"}</p>
              ) : (
              <div>
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-slate-600">{s.completed} of {s.target ?? "?"} completes</span>
                  <span className="tabular-nums text-slate-400">{Math.round(pct)}%</span>
                </div>
                <ProgressBar value={pct} tone={s.status === "closed" ? "emerald" : "indigo"} className="mt-1.5" />
              </div>
              )}
              <p className="flex items-center gap-1.5 text-xs text-slate-500">
                <CalendarClock className="size-3.5" />
                {s.status === "live" && s.deadline && <>Closes {relative(s.deadline)} · {formatDate(s.deadline)}</>}
                {s.status === "closed" && <>{s.closed_reason ? CLOSED_LABEL[s.closed_reason] : "Closed"} · {formatDate(s.closed_at)}</>}
                {s.status === "draft" && <>Created {formatDate(s.created_at)}</>}
              </p>
            </div>
          </div>
          <ChevronRight className="mt-1 size-5 shrink-0 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500" />
        </div>
      </Card>
    </Link>
  );
}
