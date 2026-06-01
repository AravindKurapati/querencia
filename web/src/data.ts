import { useEffect, useState } from "react";
import type { Snapshot } from "./types";

export function useSnapshot(): { data: Snapshot | null; error: string | null } {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const tryLoad = async () => {
      for (const path of ["/data.json", "/data.sample.json"]) {
        const r = await fetch(path);
        if (r.ok) return r.json();
      }
      throw new Error("not found");
    };
    tryLoad().then(setData).catch(() => setError("Could not load data.json"));
  }, []);
  return { data, error };
}
