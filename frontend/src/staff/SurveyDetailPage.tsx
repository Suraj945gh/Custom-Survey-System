// /surveys/:id  One survey: dashboard, questionnaire (draft editor), preview & share, versions.
// Admin-only buttons (approve, go live, deadline, close) sit in the header, each behind a confirm dialog.
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, BadgeCheck, CalendarClock, Lock, Rocket } from "lucide-react";
import { Badge, Button, ConfirmDialog, ErrorBox, Field, Skeleton, StatusChip, cx, inputClass, useToast } from "../components/ui";
import { api } from "../lib/api";
import { isAdmin, useAuth } from "../lib/auth";
import { CLOSED_LABEL, formatDateTime, localInputValue, relative } from "../lib/format";
import type { SurveyDetail } from "../lib/types";
import { DashboardTab } from "./DashboardTab";
import { PreviewTab } from "./PreviewTab";
import { QuestionnaireTab } from "./QuestionnaireTab";
import { VersionsTab } from "./VersionsTab";

const TABS = [
  { id: "overview", label: "Dashboard" },
  { id: "questionnaire", label: "Questionnaire" },
  { id: "preview", label: "Preview & share" },
  { id: "versions", label: "Versions" },
] as const;
type Tab = (typeof TABS)[number]["id"];
type Dialog = "approve" | "live" | "deadline" | "close" | null;

export function SurveyDetailPage() {
  const { id } = useParams();
  const surveyId = Number(id);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const toast = useToast();
  const [survey, setSurvey] = useState<SurveyDetail | null>(null);
  const [error, setError] = useState<{ message: string; status: number } | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [deadline, setDeadline] = useState("");

  const load = useCallback(() => {
    setError(null);
    api.getSurvey(surveyId).then(setSurvey).catch((err) => setError({ message: err.message, status: err.status }));
  }, [surveyId]);
  useEffect(load, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorBox title={error.status === 404 ? "Survey not found" : "Couldn't load this survey"} message={error.message} onRetry={error.status === 404 ? undefined : load} />
      </div>
    );
  }
  if (!survey) {
    return <div className="space-y-4"><BackLink /><Skeleton className="h-9 w-72" /><Skeleton className="h-10 w-full" /><Skeleton className="h-64 w-full" /></div>;
  }

  const defaultTab: Tab = survey.current_version_no ? "overview" : "questionnaire";
  const tab = (TABS.some((t) => t.id === params.get("tab")) ? params.get("tab") : defaultTab) as Tab;
  const admin = isAdmin(user);
  const nextVersion = (survey.versions[0]?.version_no ?? 0) + 1;
  const canApprove = admin && survey.draft?.check.ok;
  const canGoLive = admin && survey.status !== "live" && survey.current_version_no !== null;

  const act = (label: string, run: () => Promise<SurveyDetail>) => async () => {
    const updated = await run();
    setSurvey(updated);
    toast(label);
  };

  return (
    <div>
      <BackLink />
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{survey.title}</h1>
            <StatusChip status={survey.status} />
            {survey.current_version_no ? <Badge>v{survey.current_version_no}</Badge> : <Badge tone="amber">Not approved yet</Badge>}
            {survey.draft && survey.current_version_no && <Badge tone="indigo">Draft in progress</Badge>}
          </div>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            <span className="font-mono text-xs">{survey.slug}</span>
            {survey.status === "live" && survey.deadline && (
              <span className="inline-flex items-center gap-1"><CalendarClock className="size-3.5" /> Closes {relative(survey.deadline)} ({formatDateTime(survey.deadline)})</span>
            )}
            {survey.status === "closed" && (
              <span className="inline-flex items-center gap-1"><Lock className="size-3.5" /> {survey.closed_reason ? CLOSED_LABEL[survey.closed_reason] : "Closed"} · {formatDateTime(survey.closed_at)}</span>
            )}
          </p>
        </div>
        {admin && (
          <div className="flex flex-wrap gap-2">
            {canApprove && (
              <Button variant="success" icon={<BadgeCheck className="size-4" />} onClick={() => setDialog("approve")}>Approve as v{nextVersion}</Button>
            )}
            {canGoLive && (
              <Button icon={<Rocket className="size-4" />} onClick={() => {
                setDeadline(localInputValue(new Date(Date.now() + 15 * 86_400_000)));
                setDialog("live");
              }}>{survey.status === "closed" ? "Reopen" : "Go live"}</Button>
            )}
            {survey.status === "live" && (
              <>
                <Button variant="secondary" icon={<CalendarClock className="size-4" />} onClick={() => {
                  setDeadline(localInputValue(new Date(survey.deadline ?? Date.now())));
                  setDialog("deadline");
                }}>Deadline</Button>
                <Button variant="secondary" className="text-rose-600" icon={<Lock className="size-4" />} onClick={() => setDialog("close")}>Close</Button>
              </>
            )}
          </div>
        )}
      </div>

      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setParams({ tab: t.id }, { replace: true })}
            className={cx(
              "-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold transition-colors",
              tab === t.id ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="animate-enter" key={tab}>
        {tab === "overview" && <DashboardTab survey={survey} onShare={() => setParams({ tab: "preview" })} />}
        {tab === "questionnaire" && (
          // key: start the editor fresh whenever the draft appears, changes or is approved away
          <QuestionnaireTab key={survey.draft?.id ?? "no-draft"} survey={survey} onSaved={setSurvey} onDeleted={() => navigate("/surveys")} onApprove={canApprove ? () => setDialog("approve") : undefined} />
        )}
        {tab === "preview" && <PreviewTab survey={survey} />}
        {tab === "versions" && <VersionsTab survey={survey} />}
      </div>

      <ConfirmDialog
        open={dialog === "approve"}
        title={`Approve as version ${nextVersion}?`}
        confirmLabel={`Approve v${nextVersion}`}
        tone="success"
        onClose={() => setDialog(null)}
        onConfirm={act(`Approved as version ${nextVersion}`, () => api.approve(survey.id))}
      >
        <p>The draft is frozen as <strong>version {nextVersion}</strong> and can never change. Later edits become a new draft.</p>
        {survey.status === "live" && (
          <p>The survey is live: new respondents get v{nextVersion} straight away. People already halfway finish on the version they started.</p>
        )}
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog === "live"}
        title={survey.status === "closed" ? "Reopen the survey?" : "Go live?"}
        confirmLabel={survey.status === "closed" ? "Reopen" : "Go live"}
        onClose={() => setDialog(null)}
        onConfirm={act("The survey is live", () => api.goLive(survey.id, new Date(deadline).toISOString()))}
      >
        <p>Respondents can join with the share link until the deadline, or until {survey.target ?? "the target"} completes are reached.</p>
        <Field label="Deadline" htmlFor="deadline" hint="Default: 15 days from today">
          <input id="deadline" type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={inputClass} />
        </Field>
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog === "deadline"}
        title="Change the deadline"
        confirmLabel="Save deadline"
        onClose={() => setDialog(null)}
        onConfirm={act("Deadline updated", () => api.setDeadline(survey.id, new Date(deadline).toISOString()))}
      >
        <Field label="New deadline" htmlFor="new-deadline">
          <input id="new-deadline" type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={inputClass} />
        </Field>
      </ConfirmDialog>

      <ConfirmDialog
        open={dialog === "close"}
        title="Close this survey?"
        confirmLabel="Close survey"
        tone="danger"
        onClose={() => setDialog(null)}
        onConfirm={act("The survey is closed", () => api.close(survey.id))}
      >
        <p>Nobody new can join. People halfway through see “This survey is closed”; their partial answers are kept but never counted.</p>
        <p>You can reopen it later with a new deadline.</p>
      </ConfirmDialog>
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/surveys" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-900">
      <ArrowLeft className="size-4" /> Surveys
    </Link>
  );
}
