import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, type Entry } from "./api";
import EntryDialog from "./EntryDialog";
import EntryTable from "./EntryTable";
import Generator from "./Generator";
import { IconCheck, IconList, IconLock, IconPlus, IconSearch, IconSpark, IconX } from "./icons";

type Tab = "list" | "search" | "generate";
type Toast = { id: number; msg: string; kind: "ok" | "error" };

const KEYS = ["A", "B", "C", "D", "E"] as const;

export default function App() {
  const [tab, setTab] = useState<Tab>("list");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [dialog, setDialog] = useState<{ entry: Entry | null } | null>(null);
  const [toDelete, setToDelete] = useState<Entry | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  // Search tab state
  const [conds, setConds] = useState<Record<string, string>>({ A: "", B: "", C: "", D: "", E: "" });
  const [expr, setExpr] = useState("A");
  const [results, setResults] = useState<Entry[] | null>(null);
  const [searchErr, setSearchErr] = useState("");

  const notify = useCallback((msg: string, kind: "ok" | "error" = "ok") => {
    const id = ++seq.current;
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 2800);
  }, []);

  const reload = useCallback(async () => {
    try {
      setEntries(await api.list());
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => { void reload(); }, [reload]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) =>
      [e.site, e.username, ...e.keywords].some((s) => s.toLowerCase().includes(q)));
  }, [entries, filter]);

  const runSearch = async (ev?: FormEvent) => {
    ev?.preventDefault();
    setSearchErr("");
    try {
      setResults(await api.search(conds, expr));
    } catch (e) {
      setResults(null);
      setSearchErr((e as Error).message);
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await api.remove(toDelete);
      notify("削除しました");
      setResults((r) => r && r.filter((x) => x.site !== toDelete.site || x.username !== toDelete.username));
      await reload();
    } catch (e) {
      notify((e as Error).message, "error");
    }
    setToDelete(null);
  };

  const tabs: { id: Tab; label: string; icon: JSX.Element }[] = [
    { id: "list", label: "一覧", icon: <IconList /> },
    { id: "search", label: "高度検索", icon: <IconSearch /> },
    { id: "generate", label: "生成", icon: <IconSpark /> },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo"><IconLock /></span>
          <span>LocalSecretManager</span>
        </div>
        <nav className="tabs" role="tablist">
          {tabs.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id}
              className={tab === t.id ? "tab active" : "tab"} onClick={() => setTab(t.id)}>
              {t.icon}<span>{t.label}</span>
            </button>
          ))}
        </nav>
        <button className="btn btn-primary" aria-label="新規登録" onClick={() => setDialog({ entry: null })}>
          <IconPlus /> <span className="hide-sm">新規登録</span>
        </button>
      </header>

      <main className="content">
        {tab === "list" && (
          <section className="card">
            <div className="card-head">
              <div>
                <h1>登録済みパスワード</h1>
                <p className="sub">{loading ? "読み込み中…" : `全 ${entries.length} 件`}
                  {filter && !loading && ` ・ ${filtered.length} 件に絞り込み中`}</p>
              </div>
              <div className="search-box">
                <IconSearch />
                <input type="search" value={filter} placeholder="サイト名・ユーザー名・キーワードで絞り込み"
                  onChange={(e) => setFilter(e.target.value)} aria-label="絞り込み" />
              </div>
            </div>
            <EntryTable entries={filtered} notify={notify}
              onEdit={(e) => setDialog({ entry: e })} onDelete={setToDelete}
              emptyText={entries.length ? "条件に一致するパスワードはありません" : "まだ登録がありません。「新規登録」から追加しましょう"} />
          </section>
        )}

        {tab === "search" && (
          <>
            <section className="card">
              <div className="card-head">
                <div>
                  <h1>高度検索</h1>
                  <p className="sub">条件 A〜E に文字列を入力し、C言語スタイルの論理式で組み合わせます（サイト名・キーワードに含まれるかを判定）</p>
                </div>
              </div>
              <form onSubmit={runSearch} className="search-form">
                <div className="cond-grid">
                  {KEYS.map((k) => (
                    <label key={k} className="cond">
                      <span className="cond-key">{k}</span>
                      <input value={conds[k]} placeholder="含む文字列"
                        onChange={(e) => setConds({ ...conds, [k]: e.target.value })} />
                    </label>
                  ))}
                </div>
                <div className="expr-row">
                  <label className="field grow">
                    <span>論理式 <small>例: A&amp;&amp;(B||C) ／ ! も使えます</small></span>
                    <input className="mono" value={expr} onChange={(e) => setExpr(e.target.value)} spellCheck={false} />
                  </label>
                  <button type="submit" className="btn btn-primary"><IconSearch /> 検索</button>
                </div>
                {searchErr && <div className="alert" role="alert">{searchErr}</div>}
              </form>
            </section>
            {results && (
              <section className="card">
                <div className="card-head"><h2>検索結果 <span className="count">{results.length}</span></h2></div>
                <EntryTable entries={results} notify={notify}
                  onEdit={(e) => setDialog({ entry: e })} onDelete={setToDelete}
                  emptyText="該当するパスワードはありません" />
              </section>
            )}
          </>
        )}

        {tab === "generate" && (
          <section className="card narrow">
            <div className="card-head">
              <div>
                <h1>パスワード生成</h1>
                <p className="sub">使用する文字種と長さを選んで生成します（数字は常に使用）</p>
              </div>
            </div>
            <div className="card-pad"><Generator notify={notify} /></div>
          </section>
        )}
      </main>

      {dialog && (
        <EntryDialog entry={dialog.entry} existing={entries} notify={notify} onClose={() => setDialog(null)}
          onSaved={() => { setDialog(null); setResults(null); void reload(); }} />
      )}

      {toDelete && (
        <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && setToDelete(null)}>
          <div className="dialog small" role="alertdialog" aria-modal="true">
            <div className="dialog-body">
              <h2>削除しますか？</h2>
              <p>「<strong>{toDelete.site}</strong>{toDelete.username && ` (${toDelete.username})`}」のパスワードを完全に削除します。この操作は取り消せません。</p>
            </div>
            <footer>
              <button className="btn btn-ghost" onClick={() => setToDelete(null)}>キャンセル</button>
              <button className="btn btn-danger" onClick={confirmDelete} autoFocus>削除する</button>
            </footer>
          </div>
        </div>
      )}

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            {t.kind === "ok" ? <IconCheck /> : <IconX />}{t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
