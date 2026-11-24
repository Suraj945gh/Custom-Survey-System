// Check the questionnaire text while the researcher types: waits until typing pauses for a moment,
// then asks the server. Old answers that arrive late are ignored.
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { CheckResult } from "../lib/types";

export function useLiveCheck(text: string, enabled = true, delay = 450) {
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    if (!text.trim()) {
      setCheck(null);
      setChecking(false);
      return;
    }
    setChecking(true);
    const id = ++latest.current;
    const timer = setTimeout(() => {
      api.check(text)
        .then((result) => { if (id === latest.current) { setCheck(result); setError(null); } })
        .catch((err: Error) => { if (id === latest.current) setError(err.message); })
        .finally(() => { if (id === latest.current) setChecking(false); });
    }, delay);
    return () => clearTimeout(timer);
  }, [text, enabled, delay]);

  return { check, checking, error };
}
