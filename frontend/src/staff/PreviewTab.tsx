// Preview / test mode inside a phone frame, plus the share link (with a phone-friendly link for testing).
import { useEffect, useState, type ReactNode } from "react";
import { Check, Copy, ExternalLink, FlaskConical, Play, RotateCcw, Smartphone } from "lucide-react";
import { Button, Card, Notice, cx, useToast } from "../components/ui";
import { api } from "../lib/api";
import type { SurveyDetail } from "../lib/types";

export function PreviewTab({ survey }: { survey: SurveyDetail }) {
  const draftOk = Boolean(survey.draft?.check.ok);
  const choices = [
    ...(survey.draft ? [{ key: "draft", label: "Draft", ok: draftOk, useDraft: true }] : []),
    ...(survey.current_version_no ? [{ key: "current", label: `Version ${survey.current_version_no}`, ok: true, useDraft: false }] : []),
  ];
  const [pick, setPick] = useState(choices.find((c) => c.ok)?.key ?? choices[0]?.key);
  const [run, setRun] = useState<{ token: string; label: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selected = choices.find((c) => c.key === pick);

  async function start() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.testRun(survey.id, selected.useDraft);
      setRun({ token: result.token, label: selected.label });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0 space-y-5">
        <Card className="p-5">
          <h2 className="flex items-center gap-2 font-semibold text-slate-900"><FlaskConical className="size-4 text-amber-500" /> Test run</h2>
          <p className="mt-1 text-sm text-slate-500">
            Click through the survey exactly as a respondent would, with every rule working. Test answers are kept separately and never counted.
          </p>
          {choices.length === 0 ? (
            <Notice tone="warning">Save a draft first.</Notice>
          ) : (
            <>
              <div className="mt-4 flex flex-wrap gap-2" role="radiogroup" aria-label="What to preview">
                {choices.map((c) => (
                  <button key={c.key} type="button" role="radio" aria-checked={pick === c.key} onClick={() => setPick(c.key)}
                    className={cx("rounded-xl px-3.5 py-2 text-sm font-medium ring-1 transition-colors",
                      pick === c.key ? "bg-indigo-50 text-indigo-800 ring-2 ring-indigo-500" : "bg-white text-slate-700 ring-slate-200 hover:ring-slate-300")}>
                    {c.label}{!c.ok && " (has errors)"}
                  </button>
                ))}
              </div>
              {selected && !selected.ok && <div className="mt-3"><Notice tone="warning">The draft has errors. Fix them in the Questionnaire tab before previewing.</Notice></div>}
              {error && <div className="mt-3"><Notice tone="warning">{error}</Notice></div>}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={start} loading={busy} disabled={!selected?.ok} icon={run ? <RotateCcw className="size-4" /> : <Play className="size-4" />}>
                  {run ? "Start again" : "Start test run"}
                </Button>
                {run && (
                  <a href={`/r/${run.token}`} target="_blank" rel="noreferrer">
                    <Button variant="secondary" icon={<ExternalLink className="size-4" />}>Open in new tab</Button>
                  </a>
                )}
              </div>
            </>
          )}
        </Card>
        <ShareCard survey={survey} />
      </div>

      <div className="flex justify-center">
        <PhoneFrame>
          {run ? (
            <iframe key={run.token} title={`Test run of ${run.label}`} src={`/r/${run.token}`} className="h-full w-full bg-white" />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 bg-gradient-to-b from-indigo-50 to-white p-8 text-center">
              <Smartphone className="size-10 text-indigo-300" />
              <p className="text-sm font-medium text-slate-600">Start a test run to see the survey as respondents see it on their phone.</p>
            </div>
          )}
        </PhoneFrame>
      </div>
    </div>
  );
}

function PhoneFrame({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex h-[min(740px,calc(100dvh-7rem))] min-h-[560px] w-[360px] max-w-full shrink-0 flex-col rounded-[2.75rem] bg-slate-900 p-3 pt-7 shadow-2xl ring-1 ring-slate-700 lg:sticky lg:top-8">
      <div className="absolute left-1/2 top-2.5 h-1.5 w-16 -translate-x-1/2 rounded-full bg-slate-700" aria-hidden />
      <div className="flex-1 overflow-hidden rounded-[2.1rem] bg-white">{children}</div>
    </div>
  );
}

function ShareCard({ survey }: { survey: SurveyDetail }) {
  const [addresses, setAddresses] = useState<string[]>([]);
  useEffect(() => {
    api.network().then((n) => setAddresses(n.addresses)).catch(() => setAddresses([]));
  }, []);
  const path = `/s/${survey.slug}`;
  const local = `${window.location.origin}${path}`;
  const port = window.location.port ? `:${window.location.port}` : "";
  const onLocalhost = ["localhost", "127.0.0.1"].includes(window.location.hostname);

  return (
    <Card className="p-5">
      <h2 className="font-semibold text-slate-900">Share link</h2>
      {survey.status !== "live" ? (
        <p className="mt-1 text-sm text-slate-500">
          {survey.status === "closed" ? "The survey is closed, so this link shows “closed”." : "The link works once an admin puts the survey live."}
        </p>
      ) : (
        <p className="mt-1 text-sm text-slate-500">Each person enters their mobile number and gets their own private link. Answers save as they go.</p>
      )}
      <div className="mt-4 space-y-3">
        <CopyRow label="Survey link" value={local} />
        {onLocalhost && addresses.map((ip) => (
          <CopyRow key={ip} label="Open on a phone (same Wi-Fi)" value={`${window.location.protocol}//${ip}${port}${path}`} />
        ))}
      </div>
    </Card>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast("Link copied");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast("Couldn't copy. Select the link and copy it by hand.", "error");
    }
  }
  return (
    <div>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-800">{value}</code>
        <Button variant="secondary" size="sm" onClick={copy} icon={copied ? <Check className="size-4 text-emerald-600" /> : <Copy className="size-4" />}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </div>
  );
}
