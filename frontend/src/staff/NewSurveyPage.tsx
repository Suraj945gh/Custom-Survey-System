// /surveys/new  Upload or paste a questionnaire. It is checked live while you type, and every
// problem links to its line. Saving creates a draft (or a new draft of the survey with the same id).
import { useRef, useState, type DragEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, FileUp, Save, Sparkles } from "lucide-react";
import { Button, Card, Notice, useToast, cx } from "../components/ui";
import { ApiError, api } from "../lib/api";
import sampleText from "../../../samples/concave_sample_questionnaire.txt?raw";
import brokenText from "../../../samples/concave_broken_questionnaire.txt?raw";
import { CodeEditor, type EditorHandle } from "./CodeEditor";
import { CheckSummary, IssueList } from "./IssueList";
import { PageHeader } from "./StaffLayout";
import { useLiveCheck } from "./useLiveCheck";

const MAX_BYTES = 512 * 1024;

export async function readTextFile(file: File): Promise<string> {
  if (!file.name.toLowerCase().endsWith(".txt")) throw new Error("Please choose a .txt file.");
  if (file.size > MAX_BYTES) throw new Error("That file is too big (limit 512 KB).");
  return file.text();
}

export function NewSurveyPage() {
  const navigate = useNavigate();
  const toast = useToast();
  // "Copy as new wave" on a survey page sends the renamed copy here
  const copy = useLocation().state as { text?: string; copiedFrom?: string } | null;
  const editor = useRef<EditorHandle>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [text, setText] = useState(copy?.text ?? "");
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState(false); // "Paste or write instead" opens an empty editor
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { check, checking } = useLiveCheck(text);

  async function loadFile(file: File | undefined) {
    if (!file) return;
    try {
      setText(await readTextFile(file));
      setFileName(file.name);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    loadFile(e.dataTransfer.files[0]);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const survey = await api.createDraft(text, fileName);
      toast(survey.versions.length ? "Saved as a new draft of this survey" : "Draft saved");
      navigate(`/surveys/${survey.id}?tab=questionnaire`);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  const hasText = text.trim().length > 0;

  return (
    <div>
      <Link to="/surveys" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" /> Surveys
      </Link>
      <PageHeader
        title="New survey"
        subtitle="Upload the questionnaire .txt file, or paste it. Nothing goes live until an admin approves it."
        actions={hasText && (
          <Button onClick={save} loading={saving} icon={<Save className="size-4" />} disabled={checking && !check}>
            Save draft
          </Button>
        )}
      />

      {!hasText && !editing ? (
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cx(
              "flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
              dragging ? "border-indigo-400 bg-indigo-50" : "border-slate-300 bg-white",
            )}
          >
            <div className="flex size-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600"><FileUp className="size-7" /></div>
            <p className="mt-4 font-semibold text-slate-900">Drop your questionnaire here</p>
            <p className="mt-1 text-sm text-slate-500">A .txt file, up to 512 KB</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Button onClick={() => picker.current?.click()} icon={<FileUp className="size-4" />}>Choose file</Button>
              <Button variant="secondary" onClick={() => setEditing(true)}>Paste or write instead</Button>
            </div>
            <input ref={picker} type="file" accept=".txt,text/plain" className="hidden" onChange={(e) => loadFile(e.target.files?.[0])} />
            {error && <p role="alert" className="mt-4 text-sm font-medium text-rose-600">{error}</p>}
          </div>
          <Card className="p-5">
            <p className="flex items-center gap-2 font-semibold text-slate-900"><Sparkles className="size-4 text-indigo-500" /> Try an example</p>
            <p className="mt-1 text-sm text-slate-500">Load one of the files from the brief to see the checker at work.</p>
            <div className="mt-4 space-y-2">
              <ExampleButton title="Sample questionnaire" text="Smartphone study · 18 questions · passes every check"
                onClick={() => { setText(sampleText); setFileName("concave_sample_questionnaire.txt"); }} />
              <ExampleButton title="Broken questionnaire" text="Snack study · 10 planted mistakes to find"
                onClick={() => { setText(brokenText); setFileName("concave_broken_questionnaire.txt"); }} />
            </div>
          </Card>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CheckSummary check={check} checking={checking} />
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => picker.current?.click()} icon={<FileUp className="size-4" />}>Replace file</Button>
                <Button variant="ghost" size="sm" onClick={() => { setText(""); setFileName(null); setEditing(false); }}>Clear</Button>
              </div>
              <input ref={picker} type="file" accept=".txt,text/plain" className="hidden" onChange={(e) => loadFile(e.target.files?.[0])} />
            </div>
            <CodeEditor ref={editor} value={text} onChange={setText} issues={check?.issues} height="32rem" />
            {fileName && <p className="text-xs text-slate-500">From file: <span className="font-mono">{fileName}</span></p>}
          </div>
          <div className="min-w-0 space-y-3">
            <h2 className="text-sm font-semibold text-slate-900">Check result</h2>
            {copy?.copiedFrom && (
              <Notice tone="info">
                Copied from <strong>{copy.copiedFrom}</strong>. The survey id and title on line 1 were changed, so this saves as a
                separate survey. Edit anything you like, then save the draft.
              </Notice>
            )}
            {error && <Notice tone="warning">{error}</Notice>}
            {check?.error_count ? (
              <Notice tone="info">You can save a draft with errors and fix them later. It just can't be approved until they're gone.</Notice>
            ) : null}
            <IssueList check={check} onJump={(line) => editor.current?.jumpTo(line)} />
          </div>
        </div>
      )}
    </div>
  );
}

function ExampleButton({ title, text, onClick }: { title: string; text: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="w-full rounded-xl px-4 py-3 text-left ring-1 ring-slate-200 transition-colors hover:bg-slate-50 hover:ring-indigo-300">
      <span className="block text-sm font-semibold text-slate-900">{title}</span>
      <span className="block text-xs text-slate-500">{text}</span>
    </button>
  );
}
