// One input per question type, built for thumbs: big tap targets, the right phone keyboard,
// and nothing that needs a mouse. Each input gets the current answer ("draft") and reports changes.
import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Check, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import { cx, inputClass } from "../components/ui";
import type { AnswerDraft, ScreenOption, ScreenQuestion } from "../lib/types";
import { toggleOption } from "./validate";

export interface InputProps {
  question: ScreenQuestion;
  draft: AnswerDraft;
  onChange: (draft: AnswerDraft) => void;
  onSubmit: () => void; // Enter key on text inputs
  disabled?: boolean;
}

// ---------------------------------------------------------------- option cards (single, multi, dropdown)

function OptionCard({ option, selected, multi, disabled, onSelect }: {
  option: ScreenOption; selected: boolean; multi: boolean; disabled?: boolean; onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role={multi ? "checkbox" : "radio"}
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={cx(
        "flex min-h-14 w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-[15px] font-medium transition-all",
        "ring-1 active:scale-[0.99] disabled:opacity-50",
        selected ? "bg-indigo-50 text-indigo-950 ring-2 ring-indigo-500" : "bg-white text-slate-800 ring-slate-200 hover:ring-slate-300",
      )}
    >
      <span
        aria-hidden
        className={cx(
          "flex size-6 shrink-0 items-center justify-center border-2 transition-colors",
          multi ? "rounded-md" : "rounded-full",
          selected ? "border-indigo-600 bg-indigo-600 text-white" : "border-slate-300 bg-white",
        )}
      >
        {selected && (multi ? <Check className="size-4" strokeWidth={3} /> : <span className="size-2.5 rounded-full bg-white" />)}
      </span>
      <span className="min-w-0 flex-1">{option.label}</span>
    </button>
  );
}

function OtherBox({ draft, onChange, disabled, onSubmit }: Pick<InputProps, "draft" | "onChange" | "disabled" | "onSubmit">) {
  return (
    <input
      autoFocus
      aria-label="Please specify"
      placeholder="Please type here…"
      maxLength={300}
      value={draft.other_text ?? ""}
      disabled={disabled}
      onChange={(e) => onChange({ ...draft, other_text: e.target.value })}
      onKeyDown={(e) => e.key === "Enter" && onSubmit()}
      className={cx(inputClass, "mt-2 animate-enter")}
    />
  );
}

export function SingleChoice({ question, draft, onChange, disabled, onSubmit }: InputProps) {
  return (
    <div role="radiogroup" aria-label={question.text} className="space-y-2.5">
      {question.options.map((option) => {
        const selected = draft.value === option.value;
        return (
          <div key={option.value}>
            <OptionCard
              option={option}
              selected={selected}
              multi={false}
              disabled={disabled}
              onSelect={() => onChange({ value: option.value, other_text: option.other ? draft.other_text : null })}
            />
            {selected && option.other && <OtherBox draft={draft} onChange={onChange} disabled={disabled} onSubmit={onSubmit} />}
          </div>
        );
      })}
    </div>
  );
}

export function MultiChoice({ question, draft, onChange, disabled, onSubmit }: InputProps) {
  const picked = Array.isArray(draft.value) ? (draft.value as string[]) : [];
  const max = question.settings.max;
  const full = max !== undefined && picked.length >= max;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="text-slate-500">{max ? `Choose up to ${max}` : "Choose all that apply"}</span>
        <span className={cx("rounded-full px-2.5 py-0.5 text-xs font-semibold", full ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600")}>
          {picked.length}{max ? ` of ${max}` : ""} selected
        </span>
      </div>
      <div role="group" aria-label={question.text} className="space-y-2.5">
        {question.options.map((option) => {
          const selected = picked.includes(option.value);
          const blocked = !selected && full && !option.exclusive;
          return (
            <div key={option.value}>
              <OptionCard
                option={option}
                selected={selected}
                multi
                disabled={disabled || blocked}
                onSelect={() => {
                  const next = toggleOption(question, picked, option.value);
                  const keepsOther = question.options.some((o) => o.other && next.includes(o.value));
                  onChange({ value: next, other_text: keepsOther ? draft.other_text : null });
                }}
              />
              {selected && option.other && <OtherBox draft={draft} onChange={onChange} disabled={disabled} onSubmit={onSubmit} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Dropdown: a searchable list. Better than a native <select> on phones for long lists. */
export function Dropdown(props: InputProps) {
  const { question } = props;
  const [query, setQuery] = useState("");
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? question.options.filter((o) => o.label.toLowerCase().includes(q)) : question.options;
  }, [query, question.options]);
  return (
    <div>
      {question.options.length > 6 && (
        <div className="relative mb-3">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className={cx(inputClass, "pl-10")}
            aria-label="Search the options"
          />
        </div>
      )}
      {visible.length ? (
        <SingleChoice {...props} question={{ ...question, options: visible }} />
      ) : (
        <p className="rounded-xl bg-slate-100 px-4 py-6 text-center text-sm text-slate-500">No option matches “{query}”.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- yes / no and consent

export function YesNo({ question, draft, onChange, disabled }: InputProps) {
  const [yes, no] = question.options;
  const consent = question.type === "consent";
  const label = (option: ScreenOption, fallback: string) =>
    consent && ["yes", "no"].includes(option.label.toLowerCase()) ? fallback : option.label;
  const choices = [
    { option: yes, text: label(yes, "Yes, I agree"), icon: ThumbsUp, on: "bg-emerald-600 text-white ring-emerald-600" },
    { option: no, text: label(no, "No, I don't agree"), icon: ThumbsDown, on: "bg-slate-800 text-white ring-slate-800" },
  ];
  return (
    <div role="radiogroup" aria-label={question.text} className="grid grid-cols-2 gap-3">
      {choices.map(({ option, text, icon: Icon, on }) => {
        const selected = draft.value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange({ value: option.value, other_text: null })}
            className={cx(
              "flex min-h-28 flex-col items-center justify-center gap-2 rounded-2xl p-4 text-base font-semibold ring-1 transition-all active:scale-[0.98]",
              selected ? on : "bg-white text-slate-800 ring-slate-200 hover:ring-slate-300",
            )}
          >
            <Icon className="size-7" aria-hidden />
            {text}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- rating and NPS

export function Scale({ question, draft, onChange, disabled }: InputProps) {
  const nps = question.type === "nps";
  const min = question.settings.min ?? (nps ? 0 : 1);
  const max = question.settings.max ?? (nps ? 10 : 5);
  const points = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  const low = question.settings.low_label ?? (nps ? "Not at all likely" : "");
  const high = question.settings.high_label ?? (nps ? "Extremely likely" : "");
  const tint = (n: number) => !nps ? "bg-indigo-600" : n <= 6 ? "bg-rose-500" : n <= 8 ? "bg-amber-500" : "bg-emerald-500";
  const columns = nps ? "grid-cols-6 sm:grid-cols-11" : points.length <= 7 ? "" : "grid-cols-5";
  return (
    <div>
      <div
        role="radiogroup"
        aria-label={question.text}
        className={cx("grid gap-2", columns)}
        style={!nps && points.length <= 7 ? { gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` } : undefined}
      >
        {points.map((n) => {
          const selected = draft.value === n;
          return (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={String(n)}
              disabled={disabled}
              onClick={() => onChange({ value: n, other_text: null })}
              className={cx(
                "flex aspect-square max-h-16 w-full items-center justify-center rounded-2xl text-lg font-bold ring-1 transition-all active:scale-95",
                selected ? cx(tint(n), "text-white ring-transparent shadow-md") : "bg-white text-slate-700 ring-slate-200 hover:ring-slate-300",
              )}
            >
              {n}
            </button>
          );
        })}
      </div>
      {(low || high) && (
        <div className="mt-3 flex justify-between gap-4 text-xs font-medium text-slate-500">
          <span>{low && `${min} = ${low}`}</span>
          <span className="text-right">{high && `${max} = ${high}`}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- matrix (stacked cards on a phone)

export function Matrix({ question, draft, onChange, disabled }: InputProps) {
  const value = (draft.value && typeof draft.value === "object" ? draft.value : {}) as Record<string, string>;
  const done = question.rows.filter((row) => value[row]).length;
  return (
    <div>
      <p className="mb-3 text-sm text-slate-500">{done} of {question.rows.length} answered</p>
      <div className="space-y-3">
        {question.rows.map((row, i) => (
          <fieldset key={row} className={cx("rounded-2xl p-4 ring-1 transition-colors", value[row] ? "bg-white ring-slate-200" : "bg-white ring-slate-300")}>
            <legend className="sr-only">{row}</legend>
            <p className="flex gap-2 text-[15px] font-semibold text-slate-900">
              <span className={cx("flex size-6 shrink-0 items-center justify-center rounded-full text-xs", value[row] ? "bg-emerald-500 text-white" : "bg-slate-100 text-slate-500")}>
                {value[row] ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
              </span>
              {row}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {question.options.map((option) => {
                const selected = value[row] === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={selected}
                    disabled={disabled}
                    onClick={() => onChange({ value: { ...value, [row]: option.value }, other_text: null })}
                    className={cx(
                      "min-h-10 rounded-full px-3.5 py-2 text-sm font-medium ring-1 transition-all active:scale-95",
                      selected ? "bg-indigo-600 text-white ring-indigo-600" : "bg-slate-50 text-slate-700 ring-slate-200 hover:bg-white",
                    )}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- typing

function enterSubmits(onSubmit: () => void) {
  return (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };
}

export function TextAnswer({ question, draft, onChange, disabled, onSubmit }: InputProps) {
  const long = question.type === "longtext";
  const text = typeof draft.value === "string" ? draft.value : "";
  const { minlength, maxlength } = question.settings;
  const ref = useRef<HTMLTextAreaElement>(null);
  const length = text.trim().length;
  const needed = minlength ? Math.max(minlength - length, 0) : 0;
  return (
    <div>
      {long ? (
        <textarea
          ref={ref}
          autoFocus
          rows={5}
          value={text}
          maxLength={maxlength}
          disabled={disabled}
          placeholder="Type your answer…"
          onChange={(e) => onChange({ value: e.target.value, other_text: null })}
          className={cx(inputClass, "resize-y text-base leading-relaxed")}
          aria-label={question.text}
        />
      ) : (
        <input
          autoFocus
          value={text}
          maxLength={maxlength}
          disabled={disabled}
          placeholder="Type your answer…"
          onChange={(e) => onChange({ value: e.target.value, other_text: null })}
          onKeyDown={enterSubmits(onSubmit)}
          className={cx(inputClass, "text-base")}
          aria-label={question.text}
        />
      )}
      <div className="mt-2 flex justify-between text-xs text-slate-500" aria-live="polite">
        <span className={needed ? "text-amber-700" : length && minlength ? "text-emerald-700" : ""}>
          {needed ? `${needed} more character${needed === 1 ? "" : "s"} needed` : minlength && length ? "Thanks, that's enough" : ""}
        </span>
        {maxlength && <span>{text.length} / {maxlength}</span>}
      </div>
    </div>
  );
}

export function NumberAnswer({ question, draft, onChange, disabled, onSubmit }: InputProps) {
  const { min, max } = question.settings;
  const hint = min !== undefined && max !== undefined ? `Between ${min.toLocaleString("en-IN")} and ${max.toLocaleString("en-IN")}`
    : min !== undefined ? `${min} or more` : max !== undefined ? `${max} or less` : "";
  return (
    <div>
      <input
        autoFocus
        inputMode="decimal"
        value={draft.value === null || draft.value === undefined ? "" : String(draft.value)}
        disabled={disabled}
        placeholder="Enter a number"
        onChange={(e) => onChange({ value: e.target.value.replace(/[^\d.,-]/g, ""), other_text: null })}
        onKeyDown={enterSubmits(onSubmit)}
        className={cx(inputClass, "text-2xl font-semibold tracking-wide")}
        aria-label={question.text}
      />
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function FormattedAnswer({ question, draft, onChange, disabled, onSubmit }: InputProps) {
  const format = question.settings.format;
  const config = {
    pincode: { inputMode: "numeric" as const, placeholder: "6-digit pincode", maxLength: 7, type: "text", hint: "For example 400001" },
    phone: { inputMode: "tel" as const, placeholder: "10-digit mobile number", maxLength: 16, type: "tel", hint: "For example 98765 43210" },
    email: { inputMode: "email" as const, placeholder: "name@example.com", maxLength: 254, type: "email", hint: "" },
  }[format ?? "email"] ?? { inputMode: "text" as const, placeholder: "", maxLength: 200, type: "text", hint: "" };
  return (
    <div>
      <input
        autoFocus
        type={config.type}
        inputMode={config.inputMode}
        autoComplete={format === "email" ? "email" : format === "phone" ? "tel-national" : format === "pincode" ? "postal-code" : "off"}
        maxLength={config.maxLength}
        value={typeof draft.value === "string" ? draft.value : ""}
        disabled={disabled}
        placeholder={config.placeholder}
        onChange={(e) => onChange({ value: e.target.value, other_text: null })}
        onKeyDown={enterSubmits(onSubmit)}
        className={cx(inputClass, "text-xl font-semibold tracking-wider")}
        aria-label={question.text}
      />
      {config.hint && <p className="mt-2 text-xs text-slate-500">{config.hint}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- pick the right input

export function QuestionInput(props: InputProps) {
  switch (props.question.type) {
    case "single": return <SingleChoice {...props} />;
    case "multi": return <MultiChoice {...props} />;
    case "dropdown": return <Dropdown {...props} />;
    case "yesno":
    case "consent": return <YesNo {...props} />;
    case "rating":
    case "nps": return <Scale {...props} />;
    case "matrix": return <Matrix {...props} />;
    case "text":
    case "longtext": return <TextAnswer {...props} />;
    case "number": return <NumberAnswer {...props} />;
    case "formatted": return <FormattedAnswer {...props} />;
    case "info": return null;
    default: return <p className="text-sm text-slate-500">This question type can't be shown.</p>;
  }
}
