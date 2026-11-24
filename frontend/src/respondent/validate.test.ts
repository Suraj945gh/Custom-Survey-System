import { describe, expect, it } from "vitest";
import type { ScreenQuestion } from "../lib/types";
import { checkAnswer, normalisePhone, toggleOption } from "./validate";

function question(partial: Partial<ScreenQuestion>): ScreenQuestion {
  return { qid: "q1", type: "single", text: "Q", required: true, options: [], rows: [], settings: {}, ...partial };
}

const brands = question({
  type: "multi",
  settings: { max: 3 },
  options: [
    { value: "Samsung", label: "Samsung", other: false, exclusive: false },
    { value: "Apple", label: "Apple", other: false, exclusive: false },
    { value: "Vivo", label: "Vivo", other: false, exclusive: false },
    { value: "Oppo", label: "Oppo", other: false, exclusive: false },
    { value: "Other (specify)", label: "Other (specify)", other: true, exclusive: false },
    { value: "None of these", label: "None of these", other: false, exclusive: true },
  ],
});

describe("checkAnswer", () => {
  it("asks for a required answer", () => {
    expect(checkAnswer(question({}), { value: null, other_text: null })).toBe("Please answer this question.");
    expect(checkAnswer(brands, { value: [], other_text: null })).toBe("Please choose at least one option.");
  });

  it("lets optional questions stay empty", () => {
    expect(checkAnswer(question({ required: false, type: "longtext" }), { value: "", other_text: null })).toBeNull();
  });

  it("checks number ranges with the same words as the server", () => {
    const age = question({ type: "number", settings: { min: 18, max: 60 } });
    expect(checkAnswer(age, { value: "12", other_text: null })).toBe("Please enter a number from 18 to 60.");
    expect(checkAnswer(age, { value: "abc", other_text: null })).toBe("Please enter a number.");
    expect(checkAnswer(age, { value: "25", other_text: null })).toBeNull();
  });

  it("needs the Other text", () => {
    expect(checkAnswer(brands, { value: ["Other (specify)"], other_text: " " })).toBe("Please type your answer in the box.");
    expect(checkAnswer(brands, { value: ["Other (specify)"], other_text: "Nokia" })).toBeNull();
  });

  it("counts characters for long text", () => {
    const why = question({ type: "longtext", settings: { minlength: 10 } });
    expect(checkAnswer(why, { value: "too short", other_text: null })).toBe("Please write at least 10 characters (9 so far).");
  });

  it("checks pincode, phone and email", () => {
    expect(checkAnswer(question({ type: "formatted", settings: { format: "pincode" } }), { value: "01234", other_text: null })).toMatch(/pincode/);
    expect(checkAnswer(question({ type: "formatted", settings: { format: "phone" } }), { value: "+91 98765 43210", other_text: null })).toBeNull();
    expect(checkAnswer(question({ type: "formatted", settings: { format: "email" } }), { value: "a@b", other_text: null })).toMatch(/email/);
  });

  it("asks for every matrix row", () => {
    const matrix = question({ type: "matrix", rows: ["Battery", "Camera"] });
    expect(checkAnswer(matrix, { value: { Battery: "Agree" }, other_text: null })).toBe("Please answer every row (1 left).");
  });
});

describe("toggleOption (multi select)", () => {
  it("'None of these' clears every other pick", () => {
    expect(toggleOption(brands, ["Samsung", "Apple"], "None of these")).toEqual(["None of these"]);
  });

  it("picking a brand clears 'None of these'", () => {
    expect(toggleOption(brands, ["None of these"], "Apple")).toEqual(["Apple"]);
  });

  it("stops at the maximum", () => {
    expect(toggleOption(brands, ["Samsung", "Apple", "Vivo"], "Oppo")).toEqual(["Samsung", "Apple", "Vivo"]);
  });

  it("tapping again removes a pick", () => {
    expect(toggleOption(brands, ["Samsung", "Apple"], "Samsung")).toEqual(["Apple"]);
  });
});

describe("normalisePhone", () => {
  it("accepts the usual ways of writing an Indian mobile number", () => {
    for (const raw of ["9876543210", "+91 98765 43210", "09876543210", "919876543210", "98765-43210"]) {
      expect(normalisePhone(raw)).toBe("9876543210");
    }
    expect(normalisePhone("12345")).toBeNull();
    expect(normalisePhone("5876543210")).toBeNull();
  });
});
