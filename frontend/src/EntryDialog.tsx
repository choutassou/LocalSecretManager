import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Entry } from "./api";
import Generator from "./Generator";
import { IconX } from "./icons";

interface Props {
  /** Entry being edited, or null for a new one. */
  entry: Entry | null;
  /** All stored entries, used to refuse overwriting another (site, username). */
  existing: Entry[];
  onClose: () => void;
  onSaved: () => void;
  notify: (msg: string, kind?: "ok" | "error") => void;
}

export default function EntryDialog({ entry, existing, onClose, onSaved, notify }: Props) {
  const [site, setSite] = useState(entry?.site ?? "");
  const [username, setUsername] = useState(entry?.username ?? "");
  const [kws, setKws] = useState<string[]>([0, 1, 2].map((i) => entry?.keywords[i] ?? ""));
  const [password, setPassword] = useState(entry?.password ?? "");
  const [showPw, setShowPw] = useState(false);
  const [showGen, setShowGen] = useState(!entry);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => {
    first.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setError("");
    const same = (e: Entry) => e.site === site.trim() && e.username === username.trim();
    const moved = !entry || !same(entry);
    if (moved && existing.some(same)) {
      setError("同じサイト名・ユーザー名の組み合わせが既に登録されています。一覧から編集してください");
      return;
    }
    setBusy(true);
    try {
      // (site, username) is the primary key: changing either must remove the old row.
      await api.save({ site, username, keywords: kws, password });
      if (entry && (entry.site !== site.trim() || entry.username !== username.trim())) {
        await api.remove(entry);
      }
      notify(entry ? "更新しました" : "登録しました");
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="dialog" onSubmit={submit} role="dialog" aria-modal="true" aria-labelledby="dlg-title">
        <header>
          <h2 id="dlg-title">{entry ? "パスワードを編集" : "新規登録"}</h2>
          <button type="button" className="icon-btn" aria-label="閉じる" onClick={onClose}><IconX /></button>
        </header>

        <div className="dialog-body">
          {error && <div className="alert" role="alert">{error}</div>}

          <label className="field">
            <span>サイト名 / アプリ名 <em>必須</em></span>
            <input ref={first} value={site} onChange={(e) => setSite(e.target.value)} placeholder="例: GitHub" required />
          </label>

          <label className="field">
            <span>ユーザー名 <small>APIキーなどは空欄でOK</small></span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
          </label>

          <div className="field">
            <span>検索キーワード <small>3個まで・サイト名を忘れたとき用</small></span>
            <div className="kw-row">
              {kws.map((k, i) => (
                <input key={i} value={k} placeholder={`キーワード${i + 1}`}
                  onChange={(e) => setKws(kws.map((x, j) => (j === i ? e.target.value : x)))} />
              ))}
            </div>
          </div>

          <div className="field">
            <span>パスワード <em>必須</em></span>
            <div className="pw-input">
              <input type={showPw ? "text" : "password"} value={password} autoComplete="new-password"
                onChange={(e) => setPassword(e.target.value)} required />
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowPw(!showPw)}>
                {showPw ? "隠す" : "表示"}
              </button>
              <button type="button" className="btn btn-soft btn-sm" onClick={() => setShowGen(!showGen)}>
                {showGen ? "生成を閉じる" : "自動生成"}
              </button>
            </div>
            {showGen && (
              <Generator compact notify={notify} actionLabel="このパスワードを使う"
                onAction={(p) => { setPassword(p); setShowPw(true); }} />
            )}
          </div>
        </div>

        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>キャンセル</button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {entry ? "更新" : "登録"}
          </button>
        </footer>
      </form>
    </div>
  );
}
