import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import type { Screen } from "../lib/types";
import { SurveyPage } from "./SurveyPage";

const age: Screen = {
  kind: "question", survey_title: "Smartphone Usage Study", is_test: false, progress: 11, previous_qid: "q1",
  question: { qid: "q2", type: "number", text: "What is your age?", required: true, options: [], rows: [], settings: { min: 18, max: 60 } },
  answer: null,
};
const done: Screen = {
  kind: "end", survey_title: "Smartphone Usage Study", is_test: false, progress: 100, end: "completed",
  title: "Thank you!", message: "Your answers have been saved.",
};

function open() {
  render(
    <MemoryRouter initialEntries={["/r/abc"]}>
      <Routes><Route path="/r/:token" element={<SurveyPage />} /></Routes>
    </MemoryRouter>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("survey page", () => {
  it("shows the question, blocks a wrong answer in the browser, and saves a good one", async () => {
    vi.spyOn(api, "screen").mockResolvedValue(age);
    const answer = vi.spyOn(api, "answer").mockResolvedValue(done);
    window.scrollTo = vi.fn();
    const user = userEvent.setup();
    open();

    expect(await screen.findByRole("heading", { name: "What is your age?" })).toBeInTheDocument();
    expect(screen.getByText("Between 18 and 60")).toBeInTheDocument();

    await user.type(screen.getByLabelText("What is your age?"), "12");
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("Please enter a number from 18 to 60.");
    expect(answer).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText("What is your age?"));
    await user.type(screen.getByLabelText("What is your age?"), "25");
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(answer).toHaveBeenCalledWith("abc", "q2", "25", null);
    expect(await screen.findByRole("heading", { name: "Thank you!" })).toBeInTheDocument();
  });

  it("shows the server's message when the link is wrong", async () => {
    const { ApiError } = await import("../lib/api");
    vi.spyOn(api, "screen").mockRejectedValue(new ApiError(404, "This survey link is not valid."));
    open();
    expect(await screen.findByText("This survey link is not valid.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
