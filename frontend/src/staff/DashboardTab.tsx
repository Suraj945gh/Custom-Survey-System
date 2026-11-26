// Live dashboard. Refreshes every 5 seconds while the page is visible.
// Started / completed / terminated / in progress, quota groups, termination reasons, where people stop,
// and quality flags (speeders, straight-lining). Flags never remove a response.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Ban, CheckCircle2, Download, FileSpreadsheet, Flag, Hourglass, Share2, Users } from "lucide-react";
import { Badge, Button, Card, EmptyState, ErrorBox, ProgressBar, Skeleton, cx, useToast } from "../components/ui";
import { api } from "../lib/api";
import { plural, relative } from "../lib/format";
import type { Dashboard, SurveyDetail } from "../lib/types";

const REFRESH_MS = 5000;

export function DashboardTab({ survey, onShare }: { survey: SurveyDetail; onShare: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"csv" | "xlsx" | null>(null);
  const [, tick] = useState(0); // re-render so "updated 3s ago" stays true

  const load = useCallback(() => {
    api.dashboard(survey.id).then((d) => { setData(d); setError(null); }).catch((err: Error) => setError(err.message));
  }, [survey.id]);

  useEffect(() => {
    load();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") load();
      tick((n) => n + 1);
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  async function download(format: "csv" | "xlsx") {
    setExporting(format);
    try {
      await api.exportFile(survey.id, survey.slug, format);
    } catch (err) {
      toast((err as Error).message, "error");
    } finally {
      setExporting(null);
    }
  }

  if (!survey.current_version_no) {
    return (
      <EmptyState icon={<Users className="size-6" />} title="Not running yet"
        text="Once a version is approved and the survey goes live, the numbers appear here and update by themselves." />
    );
  }
  if (error && !data) return <ErrorBox title="Couldn't load the dashboard" message={error} onRetry={load} />;
  if (!data) {
    return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}<Skeleton className="h-64 rounded-2xl sm:col-span-2 lg:col-span-4" /></div>;
  }

  const maxReason = Math.max(1, ...data.reasons.map((r) => r.count));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-xs font-medium text-slate-500" aria-live="polite">
          <span className={cx("size-2 rounded-full", error ? "bg-amber-400" : "bg-emerald-500 animate-pulse")} />
          {error ? "Reconnecting…" : `Live · updated ${relative(data.updated_at)}`}
          {data.test_runs > 0 && <Badge tone="amber">{plural(data.test_runs, "test run")} not counted</Badge>}
        </p>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" icon={<Download className="size-4" />} loading={exporting === "csv"} onClick={() => download("csv")}>CSV</Button>
          <Button variant="secondary" size="sm" icon={<FileSpreadsheet className="size-4" />} loading={exporting === "xlsx"} onClick={() => download("xlsx")}>Excel</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card className="col-span-2 p-5 lg:col-span-1">
          <p className="flex items-center gap-2 text-sm font-medium text-slate-500"><CheckCircle2 className="size-4 text-emerald-500" /> Completed</p>
          <p className="mt-2 text-3xl font-bold tabular-nums">{data.completed}<span className="text-lg font-semibold text-slate-400"> / {data.target ?? "?"}</span></p>
          <ProgressBar value={data.target ? (100 * data.completed) / data.target : 0} tone="emerald" className="mt-3" label="Completes towards target" />
          <p className="mt-1.5 text-xs text-slate-500">{data.progress}% of target</p>
        </Card>
        <Stat icon={<Users className="size-4 text-indigo-500" />} label="Started" value={data.started} note="everyone who opened their link" />
        <Stat icon={<Hourglass className="size-4 text-amber-500" />} label="In progress" value={data.in_progress} note="never counted until they finish" />
        <Stat icon={<Ban className="size-4 text-rose-500" />} label="Terminated" value={data.terminated} note="screened out or quota full" />
      </div>

      {data.started === 0 && (
        <EmptyState icon={<Share2 className="size-6" />} title="No responses yet"
          text={survey.status === "live" ? "Share the survey link. Every answer shows up here within a few seconds." : "Go live to start collecting responses."}
          action={survey.status === "live" ? <Button onClick={onShare} icon={<Share2 className="size-4" />}>Get the share link</Button> : undefined} />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-semibold text-slate-900">Quota groups</h2>
          {data.quotas.length === 0 ? <p className="mt-3 text-sm text-slate-500">This survey has no quotas.</p> : (
            <ul className="mt-4 space-y-4">
              {data.quotas.map((q) => (
                <li key={`${q.question}-${q.value}`}>
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-medium text-slate-800">{q.value} <span className="font-mono text-xs text-slate-400">{q.question}</span></span>
                    <span className="tabular-nums text-slate-600">
                      {q.done} / {q.target} {q.full ? <Badge tone="rose">Full</Badge> : <span className="text-slate-400">· {q.left} left</span>}
                    </span>
                  </div>
                  <ProgressBar value={(100 * q.done) / q.target} tone={q.full ? "rose" : "indigo"} className="mt-1.5" label={`${q.value} quota`} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-slate-900">Termination reasons</h2>
          {data.reasons.length === 0 ? <p className="mt-3 text-sm text-slate-500">Nobody has been screened out yet.</p> : (
            <ul className="mt-4 space-y-3">
              {data.reasons.map((r) => (
                <li key={r.reason}>
                  <div className="flex justify-between gap-3 text-sm"><span className="text-slate-800">{r.reason}</span><span className="font-semibold tabular-nums">{r.count}</span></div>
                  <ProgressBar value={(100 * r.count) / maxReason} tone="rose" className="mt-1.5 h-1.5" label={r.reason} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-slate-900">Where people stopped</h2>
          <p className="text-xs text-slate-500">Last question answered by people still in progress</p>
          {data.drop_off.length === 0 ? <p className="mt-3 text-sm text-slate-500">Nobody is stuck halfway.</p> : (
            <ul className="mt-3 divide-y divide-slate-100 text-sm">
              {data.drop_off.map((d) => (
                <li key={d.question} className="flex justify-between py-2"><span className="font-mono text-slate-700">{d.question}</span><span className="font-semibold tabular-nums">{d.count}</span></li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h2 className="font-semibold text-slate-900">By version</h2>
          {data.versions.length === 0 ? <p className="mt-3 text-sm text-slate-500">No responses yet.</p> : (
            <table className="mt-3 w-full text-sm">
              <thead><tr className="text-left text-xs text-slate-500"><th className="py-1 font-medium">Version</th><th className="py-1 font-medium">Started</th><th className="py-1 font-medium">Completed</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {data.versions.map((v) => (
                  <tr key={String(v.version_no)}><td className="py-2 font-semibold">v{v.version_no}</td><td className="py-2 tabular-nums">{v.started}</td><td className="py-2 tabular-nums">{v.completed}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="p-5 lg:col-span-2">
          <h2 className="flex items-center gap-2 font-semibold text-slate-900"><Flag className="size-4 text-amber-500" /> Quality flags</h2>
          <p className="text-xs text-slate-500">
            Speeder: under 2 seconds per question, or under a third of the typical time. Straight-lining: the same answer on every matrix row.
            The time shown is how long that person took from joining to finishing. Flags never remove a response; they are also in the export.
          </p>
          {data.quality.checked === 0 ? <p className="mt-3 text-sm text-slate-500">Flags appear once people complete the survey.</p> : (
            <>
              <p className="mt-3 text-sm text-slate-700">
                <strong className="tabular-nums">{plural(data.quality.speeders, "speeder")}</strong> ·{" "}
                <strong className="tabular-nums">{plural(data.quality.straight_liners, "straight-liner")}</strong>{" "}
                <span className="text-slate-500">out of {plural(data.quality.checked, "complete")}</span>
              </p>
              {data.quality.flagged.length > 0 && (
                <ul className="mt-3 divide-y divide-slate-100 text-sm">
                  {data.quality.flagged.map((f) => (
                    <li key={f.respondent_id ?? f.flags.join()} className="flex flex-wrap items-center justify-between gap-2 py-2">
                      <span className="font-medium text-slate-700">Respondent {f.respondent_id}</span>
                      <span className="flex flex-wrap items-center gap-2">
                        {f.flags.map((flag) => <Badge key={flag} tone="amber">{flag}</Badge>)}
                        <span className="text-xs tabular-nums text-slate-500" title="Time from joining to finishing">took {duration(f.seconds)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

function duration(seconds: number) {
  const m = Math.floor(seconds / 60);
  return m ? `${m} min ${seconds % 60} s` : `${seconds} s`;
}

function Stat({ icon, label, value, note }: { icon: ReactNode; label: string; value: number; note: string }) {
  return (
    <Card className="p-4 sm:p-5">
      <p className="flex items-center gap-2 text-sm font-medium text-slate-500">{icon} {label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums">{value}</p>
      <p className="mt-1 hidden text-xs text-slate-400 sm:block">{note}</p>
    </Card>
  );
}
