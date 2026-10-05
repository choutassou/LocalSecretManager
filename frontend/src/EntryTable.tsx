import { useState } from "react";
import type { Entry } from "./api";
import { IconCopy, IconEdit, IconEye, IconEyeOff, IconKey, IconTrash } from "./icons";

interface Props {
  entries: Entry[];
  notify: (msg: string, kind?: "ok" | "error") => void;
  onEdit: (e: Entry) => void;
  onDelete: (e: Entry) => void;
  emptyText: string;
}

const copy = async (text: string, notify: Props["notify"], what: string) => {
  try {
    await navigator.clipboard.writeText(text);
    notify(`${what}をコピーしました`);
  } catch {
    notify("コピーに失敗しました", "error");
  }
};

export default function EntryTable({ entries, notify, onEdit, onDelete, emptyText }: Props) {
  const [shown, setShown] = useState<Set<string>>(new Set());

  // (site, username) is the primary key; "\u0000" cannot occur in either part.
  const idOf = (e: Entry) => `${e.site}\u0000${e.username}`;
  const toggle = (id: string) =>
    setShown((s) => {
      const n = new Set(s);
      if (!n.delete(id)) n.add(id);
      return n;
    });

  if (!entries.length) {
    return (
      <div className="empty-state">
        <IconKey />
        <p>{emptyText}</p>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table className="entries">
        <thead>
          <tr>
            <th>サイト / アプリ</th>
            <th>ユーザー名</th>
            <th>キーワード</th>
            <th>パスワード</th>
            <th aria-label="操作" />
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const id = idOf(e);
            const visible = shown.has(id);
            return (
              <tr key={id} data-testid="entry-row">
                <td data-label="サイト / アプリ">
                  <div className="site">
                    <span className="avatar" aria-hidden>{e.site.trim().charAt(0).toUpperCase()}</span>
                    <strong>{e.site}</strong>
                  </div>
                </td>
                <td data-label="ユーザー名">
                  {e.username ? (
                    <span className="copyable">
                      {e.username}
                      <button className="icon-btn sm" title="ユーザー名をコピー" aria-label="ユーザー名をコピー"
                        onClick={() => copy(e.username, notify, "ユーザー名")}>
                        <IconCopy />
                      </button>
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td data-label="キーワード">
                  {e.keywords.length ? (
                    <div className="tags">{e.keywords.map((k) => <span className="tag" key={k}>{k}</span>)}</div>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td data-label="パスワード">
                  <span className="pw">
                    <code className={visible ? "" : "masked"}>{visible ? e.password : "••••••••••"}</code>
                    <button className="icon-btn sm" title={visible ? "隠す" : "表示"} aria-label={visible ? "隠す" : "表示"}
                      onClick={() => toggle(id)}>
                      {visible ? <IconEyeOff /> : <IconEye />}
                    </button>
                    <button className="icon-btn sm" title="パスワードをコピー" aria-label="パスワードをコピー"
                      onClick={() => copy(e.password, notify, "パスワード")}>
                      <IconCopy />
                    </button>
                  </span>
                </td>
                <td className="actions">
                  <button className="icon-btn" title="編集" aria-label="編集" onClick={() => onEdit(e)}>
                    <IconEdit />
                  </button>
                  <button className="icon-btn danger" title="削除" aria-label="削除" onClick={() => onDelete(e)}>
                    <IconTrash />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
