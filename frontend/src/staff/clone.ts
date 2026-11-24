// Bonus "Clone": copy a survey's questionnaire to start a second wave.
// The copy must be a SEPARATE survey, and a survey is identified by <survey id="...">, so we give
// the copy a new id (smartphone_study -> smartphone_study_wave2) and a new title ("... (Wave 2)").
// If that id is already taken, we try wave3, wave4, ...

const SURVEY_TAG = /<survey\b[^>]*>/i;
const WAVE = /_wave(\d+)$/i;
const TITLE_WAVE = /\s*\(Wave \d+\)\s*$/i;

function attribute(tag: string, name: string): string | null {
  const match = tag.match(new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`, "i"));
  return match ? match[1] : null;
}

function withAttribute(tag: string, name: string, value: string): string {
  const pattern = new RegExp(`(\\b${name}\\s*=\\s*")[^"]*(")`, "i");
  return pattern.test(tag) ? tag.replace(pattern, `$1${value}$2`) : tag.replace(/>$/, ` ${name}="${value}">`);
}

/** The questionnaire text with a new survey id and title for the next wave. */
export function nextWave(text: string, takenIds: Iterable<string>): { text: string; id: string; title: string } {
  const tag = text.match(SURVEY_TAG)?.[0];
  if (!tag) return { text, id: "", title: "" }; // nothing to rename; the checker will explain
  const taken = new Set([...takenIds].map((id) => id.toLowerCase()));

  const oldId = attribute(tag, "id") ?? "survey";
  const base = oldId.replace(WAVE, "");
  let wave = Number(oldId.match(WAVE)?.[1] ?? 1) + 1;
  while (taken.has(`${base}_wave${wave}`.toLowerCase())) wave++;
  const id = `${base}_wave${wave}`;

  const oldTitle = attribute(tag, "title") ?? base;
  const title = `${oldTitle.replace(TITLE_WAVE, "")} (Wave ${wave})`;

  const newTag = withAttribute(withAttribute(tag, "id", id), "title", title);
  return { text: text.replace(tag, newTag), id, title };
}
