// A plain text editor with line numbers. Lines with an error get a red mark; clicking a
// problem in the list calls jumpTo(line) to move the cursor there.
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import { cx } from "../components/ui";
import type { Issue } from "../lib/types";

export interface EditorHandle {
  jumpTo: (line: number) => void;
}

const LINE_HEIGHT = 22; // px; the gutter and the textarea must use the same value

export const CodeEditor = forwardRef<EditorHandle, {
  value: string;
  onChange?: (value: string) => void;
  issues?: Issue[];
  readOnly?: boolean;
  height?: string;
}>(function CodeEditor({ value, onChange, issues = [], readOnly, height = "28rem" }, ref) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const gutter = useRef<HTMLDivElement>(null);
  const lineCount = Math.max(1, value.split("\n").length);

  // line number -> "error" | "warning" (errors win)
  const marks = useMemo(() => {
    const map = new Map<number, Issue["severity"]>();
    for (const issue of issues) {
      if (map.get(issue.line) !== "error") map.set(issue.line, issue.severity);
    }
    return map;
  }, [issues]);

  useImperativeHandle(ref, () => ({
    jumpTo(line: number) {
      const el = textarea.current;
      if (!el) return;
      const lines = value.split("\n");
      const start = lines.slice(0, line - 1).reduce((n, l) => n + l.length + 1, 0);
      const end = start + (lines[line - 1]?.length ?? 0);
      el.focus();
      el.setSelectionRange(start, end);
      el.scrollTop = Math.max(0, (line - 4) * LINE_HEIGHT);
    },
  }), [value]);

  return (
    <div
      className="relative flex overflow-hidden rounded-xl bg-slate-950 font-mono text-[13px] ring-1 ring-slate-800"
      style={{ height }}
    >
      <div
        ref={gutter}
        aria-hidden
        className="w-12 shrink-0 select-none overflow-hidden border-r border-slate-800 bg-slate-900 py-3 text-right text-slate-500"
      >
        {Array.from({ length: lineCount }, (_, i) => {
          const mark = marks.get(i + 1);
          return (
            <div
              key={i}
              style={{ height: LINE_HEIGHT, lineHeight: `${LINE_HEIGHT}px` }}
              className={cx("relative pr-2.5 tabular-nums", mark === "error" && "bg-rose-500/15 font-bold text-rose-400", mark === "warning" && "text-amber-400")}
            >
              {mark && <span className={cx("absolute left-1.5 top-1/2 size-1.5 -translate-y-1/2 rounded-full", mark === "error" ? "bg-rose-500" : "bg-amber-400")} />}
              {i + 1}
            </div>
          );
        })}
      </div>
      <textarea
        ref={textarea}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange?.(e.target.value)}
        onScroll={(e) => { if (gutter.current) gutter.current.scrollTop = e.currentTarget.scrollTop; }}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        wrap="off"
        aria-label="Questionnaire file"
        placeholder={readOnly ? "" : '<survey id="my_study" title="My study" target="200">\n  <question id="q1" type="consent" required>\n    <text>Do you agree to take part?</text>\n  </question>\n</survey>'}
        className="flex-1 resize-none bg-transparent px-3 py-3 text-slate-100 caret-indigo-400 outline-none placeholder:text-slate-600 selection:bg-indigo-500/40"
        style={{ lineHeight: `${LINE_HEIGHT}px`, tabSize: 2 }}
      />
    </div>
  );
});
