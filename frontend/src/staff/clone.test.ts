import { describe, expect, it } from "vitest";
import { nextWave } from "./clone";

const FILE = `<survey id="smartphone_study" title="Smartphone Usage Study" target="200">
<question id="q1" type="consent" required><text>Agree?</text></question>
</survey>`;

describe("nextWave", () => {
  it("gives the copy a new id and title, and keeps the rest", () => {
    const copy = nextWave(FILE, ["smartphone_study"]);
    expect(copy.id).toBe("smartphone_study_wave2");
    expect(copy.title).toBe("Smartphone Usage Study (Wave 2)");
    expect(copy.text.split("\n")[0]).toBe('<survey id="smartphone_study_wave2" title="Smartphone Usage Study (Wave 2)" target="200">');
    expect(copy.text.split("\n").slice(1)).toEqual(FILE.split("\n").slice(1));
  });

  it("counts on from an existing wave and skips ids already taken", () => {
    const wave2 = nextWave(FILE, []).text;
    const copy = nextWave(wave2, ["smartphone_study", "smartphone_study_wave2", "smartphone_study_wave3"]);
    expect(copy.id).toBe("smartphone_study_wave4");
    expect(copy.title).toBe("Smartphone Usage Study (Wave 4)");
  });

  it("adds a title when the file had none, and leaves broken files alone", () => {
    expect(nextWave('<survey id="s1">\n</survey>', []).text).toContain('<survey id="s1_wave2" title="s1 (Wave 2)">');
    expect(nextWave("no survey tag here", []).text).toBe("no survey tag here");
  });
});
