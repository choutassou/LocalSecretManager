export interface Entry {
  site: string;
  username: string;
  keywords: string[];
  password: string;
}

export interface GenOptions {
  upper: boolean;
  lower: boolean;
  symbol: boolean;
  min: number;
  max: number;
}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
  return j as T;
}

export const api = {
  list: () => post<{ results: Entry[] }>("/api/list").then((r) => r.results),
  search: (conditions: Record<string, string>, expression: string) =>
    post<{ results: Entry[] }>("/api/search", { conditions, expression }).then((r) => r.results),
  save: (e: Entry) => post<{ ok: true }>("/api/entries", e),
  remove: (e: Pick<Entry, "site" | "username">) =>
    post<{ ok: true }>("/api/delete", { site: e.site, username: e.username }),
  generate: (o: GenOptions) => post<{ password: string }>("/api/generate", o).then((r) => r.password),
};
