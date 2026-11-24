// The list of problems found in a file. Each row jumps to its line in the editor.
import { AlertCircle, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { cx } from "../components/ui";
import type { CheckResult } from "../lib/types";
import { plural } from "../lib/format";

export function CheckSummary({ check, checking }: { check: CheckResult | null; checking?: boolean }) {
  if (checking && !check) {
    return <span className="inline-flex items-center gap-1.5 text-sm text-slate-500"><Loader2 className="size-4 animate-spin" /> Checking…</span>;
  }
  if (!check) return null;
  const parts = check.survey ? [plural(check.survey.questions, "question"), plural(check.survey.quotas, "quota")] : [];
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {check.error_count ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 font-semibold text-rose-700 ring-1 ring-rose-200">
          <AlertCircle className="size-4" /> {plural(check.error_count, "error")}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 font-semibold text-emerald-700 ring-1 ring-emerald-200">
          <CheckCircle2 className="size-4" /> No errors
        </span>
      )}
      {check.warning_count > 0 && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 font-semibold text-amber-800 ring-1 ring-amber-200">
          <AlertTriangle className="size-4" /> {plural(check.warning_count, "warning")}
        </span>
      )}
      {parts.length > 0 && <span className="text-slate-500">{parts.join(" · ")}</span>}
      {checking && <Loader2 className="size-4 animate-spin text-slate-400" aria-label="Checking again" />}
    </div>
  );
}

export function IssueList({ check, onJump }: { check: CheckResult | null; onJump: (line: number) => void }) {
  if (!check) return null;
  if (!check.issues.length) {
    return (
      <div className="flex items-center gap-3 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900 ring-1 ring-emerald-200">
        <CheckCircle2 className="size-5 shrink-0 text-emerald-500" />
        <div>
          <p className="font-semibold">The file looks good</p>
          <p className="text-emerald-800">Every question, rule and quota was checked. You can preview it or send it for approval.</p>
        </div>
      </div>
    );
  }
  return (
    <ol className="divide-y divide-slate-100 overflow-hidden rounded-xl bg-white ring-1 ring-slate-200" aria-label="Problems in the file">
      {check.issues.map((issue, i) => {
        const error = issue.severity === "error";
        return (
          <li key={`${issue.line}-${issue.code}-${i}`}>
            <button
              type="button"
              onClick={() => onJump(issue.line)}
              className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50"
            >
              {error ? <AlertCircle className="mt-0.5 size-4 shrink-0 text-rose-500" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" />}
              <span className={cx("shrink-0 rounded-md px-1.5 py-0.5 font-mono text-xs font-semibold", error ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800")}>
                Line {issue.line}
              </span>
              <span className="min-w-0 text-sm text-slate-700">{issue.message}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
