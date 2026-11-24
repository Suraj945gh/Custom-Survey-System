import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { AnswerDraft, ScreenQuestion } from "../lib/types";
import { QuestionInput } from "./inputs";

const brands: ScreenQuestion = {
  qid: "q6", type: "multi", text: "Which brands?", required: true, rows: [], settings: { max: 3 },
  options: [
    { value: "Samsung", label: "Samsung", other: false, exclusive: false },
    { value: "Apple", label: "Apple", other: false, exclusive: false },
    { value: "Other (specify)", label: "Other (specify)", other: true, exclusive: false },
    { value: "None of these", label: "None of these", other: false, exclusive: true },
  ],
};

/** Renders an input the way the survey page does: it keeps the answer in state. */
function Harness({ question, onDraft }: { question: ScreenQuestion; onDraft?: (d: AnswerDraft) => void }) {
  const [draft, setDraft] = useState<AnswerDraft>({ value: question.type === "multi" ? [] : null, other_text: null });
  return (
    <QuestionInput
      question={question}
      draft={draft}
      onChange={(d) => { setDraft(d); onDraft?.(d); }}
      onSubmit={() => {}}
    />
  );
}

describe("multi select", () => {
  it("shows a live counter and 'None of these' clears the other picks", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness question={brands} onDraft={onDraft} />);

    await user.click(screen.getByRole("checkbox", { name: "Samsung" }));
    await user.click(screen.getByRole("checkbox", { name: "Apple" }));
    expect(screen.getByText("2 of 3 selected")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "None of these" }));
    expect(screen.getByRole("checkbox", { name: "None of these" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("checkbox", { name: "Samsung" })).toHaveAttribute("aria-checked", "false");
    expect(onDraft).toHaveBeenLastCalledWith({ value: ["None of these"], other_text: null });
  });

  it("opens a text box for Other and keeps the typed text", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    render(<Harness question={brands} onDraft={onDraft} />);
    await user.click(screen.getByRole("checkbox", { name: "Other (specify)" }));
    await user.type(screen.getByLabelText("Please specify"), "Nokia");
    expect(onDraft).toHaveBeenLastCalledWith({ value: ["Other (specify)"], other_text: "Nokia" });
  });
});

describe("rating", () => {
  it("shows one button per point with the end labels", async () => {
    const user = userEvent.setup();
    const onDraft = vi.fn();
    const rating: ScreenQuestion = {
      qid: "q8", type: "rating", text: "How happy?", required: true, rows: [], options: [],
      settings: { min: 1, max: 5, low_label: "Very unhappy", high_label: "Very happy" },
    };
    render(<Harness question={rating} onDraft={onDraft} />);
    expect(screen.getAllByRole("radio")).toHaveLength(5);
    expect(screen.getByText("1 = Very unhappy")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "4" }));
    expect(onDraft).toHaveBeenLastCalledWith({ value: 4, other_text: null });
  });
});
