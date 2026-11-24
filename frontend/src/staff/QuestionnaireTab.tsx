// The draft editor: edit or replace the file, see problems live, save, discard.
// With no draft, it shows the current version (read-only) and offers to start a new draft from it.
import { useEffect, useRef, useState } from "react";
import { FilePenLine, FileUp, Save, Trash2 } from "lucide-react";
import { Badge, Button, ConfirmDialog, Notice, Skeleton, useToast } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { isAdmin, useAuth } from "../lib/auth";
import { formatDateTime } from "../lib/format";
import type { SurveyDetail } from "../lib/types";
import { CodeEditor, type EditorHandle } from "./CodeEditor";
import { CheckSummary, IssueList } from "./IssueList";
import { readTextFile } from "./NewSurveyPage";
import { useLiveCheck } from "./useLiveCheck";

export function QuestionnaireTab({ survey, onSaved, onDeleted, onApprove }: {
  survey: SurveyDetail;
  onSaved: (s: SurveyDetail) => void;
  onDeleted: () => void;
  onApprove?: () => void;
}) {
  const { user } = useAuth();
  const toast = useToast();
  const editor = useRef<EditorHandle>(null);
  const picker = useRef<HTMLInputElement>(null);
  const draft = survey.draft;
  const [text, setText] = useState(draft?.text ?? "");
  const [editing, setEditing] = useState(Boolean(draft));
  const [versionText, setVersionText] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const dirty = editing && text !== (draft?.text ?? versionText ?? "");
  const live = useLiveCheck(text, editing && dirty);
  const check = dirty ? live.check : draft?.check ?? null;

  // No draft: show the current version's file.
  useEffect(() => {
    if (draft || !survey.current_version_no) return;
    api.version(survey.id, survey.current_version_no).then((v) => setVersionText(v.text)).catch((err) => setError(err.message));
  }, [draft, survey.id, survey.current_version_no]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateDraft(survey.id, text);
      onSaved(updated);
      toast(updated.draft?.check.ok ? "Draft saved. No errors." : "Draft saved");
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function replace(file?: File) {
    if (!file) return;
    try {
      setText(await readTextFile(file));
      setEditing(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!editing) {
    if (versionText === null) return error ? <Notice tone="warning">{error}</Notice> : <Skeleton className="h-96 w-full" />;
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-slate-600">Showing <strong>version {survey.current_version_no}</strong> (approved, read-only).</p>
          <div className="flex gap-2">
            <Button variant="secondary" icon={<FileUp className="size-4" />} onClick={() => picker.current?.click()}>Upload new file</Button>
            <Button icon={<FilePenLine className="size-4" />} onClick={() => { setText(versionText); setEditing(true); }}>Edit as new draft</Button>
          </div>
          <input ref={picker} type="file" accept=".txt,text/plain" className="hidden" onChange={(e) => replace(e.target.files?.[0])} />
        </div>
        <CodeEditor value={versionText} readOnly height="32rem" />
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <CheckSummary check={check} checking={live.checking && dirty} />
            {dirty && <Badge tone="amber">Unsaved changes</Badge>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" icon={<FileUp className="size-4" />} onClick={() => picker.current?.click()}>Replace file</Button>
            {draft && <Button variant="ghost" size="sm" className="text-rose-600" icon={<Trash2 className="size-4" />} onClick={() => setConfirmDiscard(true)}>Discard draft</Button>}
            <Button size="sm" icon={<Save className="size-4" />} loading={saving} disabled={!dirty && Boolean(draft)} onClick={save}>
              {draft ? "Save & re-check" : "Save as draft"}
            </Button>
          </div>
          <input ref={picker} type="file" accept=".txt,text/plain" className="hidden" onChange={(e) => replace(e.target.files?.[0])} />
        </div>
        <CodeEditor ref={editor} value={text} onChange={setText} issues={check?.issues} height="34rem" />
        {draft && !dirty && (
          <p className="text-xs text-slate-500">Draft saved {formatDateTime(draft.updated_at)}{draft.updated_by ? ` by ${draft.updated_by}` : ""}{draft.file_name ? ` · ${draft.file_name}` : ""}</p>
        )}
      </div>

      <div className="min-w-0 space-y-3">
        <h2 className="text-sm font-semibold text-slate-900">Check result</h2>
        {error && <Notice tone="warning">{error}</Notice>}
        {draft?.check.ok && !dirty && (
          isAdmin(user) ? (
            <Notice tone="success">
              Ready to approve.{" "}
              {onApprove && <button type="button" onClick={onApprove} className="font-semibold underline underline-offset-2">Approve now</button>}
            </Notice>
          ) : (
            <Notice tone="success">Ready. An admin needs to approve this draft before it can go live. You can preview it first.</Notice>
          )
        )}
        <IssueList check={check} onJump={(line) => editor.current?.jumpTo(line)} />
      </div>

      <ConfirmDialog
        open={confirmDiscard}
        title="Discard this draft?"
        confirmLabel="Discard"
        tone="danger"
        onClose={() => setConfirmDiscard(false)}
        onConfirm={async () => {
          await api.discardDraft(survey.id);
          toast("Draft discarded");
          if (!survey.current_version_no) onDeleted();
          else onSaved(await api.getSurvey(survey.id));
        }}
      >
        {survey.current_version_no
          ? <p>Your changes are deleted. Version {survey.current_version_no} stays as it is.</p>
          : <p>This survey was never approved, so the whole survey is deleted.</p>}
      </ConfirmDialog>
    </div>
  );
}
