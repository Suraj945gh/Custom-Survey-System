// Every approved (frozen) version, newest first. Open one to see its exact file.
import { useState } from "react";
import { ChevronDown, History } from "lucide-react";
import { Card, EmptyState, ErrorBox, Skeleton, cx } from "../components/ui";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import type { SurveyDetail, VersionDetail } from "../lib/types";
import { CodeEditor } from "./CodeEditor";

export function VersionsTab({ survey }: { survey: SurveyDetail }) {
  const [open, setOpen] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, VersionDetail>>({});
  const [error, setError] = useState<string | null>(null);

  if (survey.versions.length === 0) {
    return <EmptyState icon={<History className="size-6" />} title="No versions yet" text="A draft becomes version 1 when an admin approves it. Each approved version is frozen forever." />;
  }

  function toggle(no: number) {
    setOpen(open === no ? null : no);
    if (!details[no]) {
      api.version(survey.id, no).then((v) => setDetails((d) => ({ ...d, [no]: v }))).catch((err) => setError(err.message));
    }
  }

  return (
    <div className="space-y-3">
      {error && <ErrorBox message={error} />}
      {survey.versions.map((v, i) => (
        <Card key={v.id} className="overflow-hidden">
          <button type="button" onClick={() => toggle(v.version_no)} className="flex w-full items-center gap-4 p-4 text-left hover:bg-slate-50" aria-expanded={open === v.version_no}>
            <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold", i === 0 ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600")}>
              v{v.version_no}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-slate-900">
                Version {v.version_no} {i === 0 && <span className="ml-1 text-xs font-medium text-indigo-600">current</span>}
              </span>
              <span className="block truncate text-xs text-slate-500">
                Approved {formatDateTime(v.approved_at)}{v.approved_by ? ` by ${v.approved_by}` : ""} · {v.question_count} questions{v.file_name ? ` · ${v.file_name}` : ""}
              </span>
            </span>
            <ChevronDown className={cx("size-5 text-slate-400 transition-transform", open === v.version_no && "rotate-180")} />
          </button>
          {open === v.version_no && (
            <div className="border-t border-slate-100 p-4">
              {details[v.version_no] ? <CodeEditor value={details[v.version_no].text} readOnly height="24rem" /> : <Skeleton className="h-64 w-full" />}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
