import { useState } from "react";
import { api, type GenOptions } from "./api";
import { IconCheck, IconCopy, IconRefresh } from "./icons";

interface Props {
  /** Called whenever a new password is generated. */
  onGenerate?: (pw: string) => void;
  notify: (msg: string, kind?: "ok" | "error") => void;
  compact?: boolean;
  /** Label of an optional extra action button shown next to the result. */
  actionLabel?: string;
  onAction?: (pw: string) => void;
}

export default function Generator({ onGenerate, notify, compact, actionLabel, onAction }: Props) {
  const [opt, setOpt] = useState<GenOptions>({ upper: true, lower: true, symbol: true, min: 8, max: 64 });
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  const generate = async () => {
    setBusy(true);
    try {
      const p = await api.generate(opt);
      setPw(p);
      onGenerate?.(p);
    } catch (e) {
      notify((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(pw);
    notify("コピーしました");
  };

  const toggle = (k: "upper" | "lower" | "symbol", label: string) => (
    <label className="chip">
      <input type="checkbox" checked={opt[k]} onChange={(e) => setOpt({ ...opt, [k]: e.target.checked })} />
      <span>{label}</span>
    </label>
  );

  return (
    <div className={compact ? "gen gen-compact" : "gen"}>
      <div className="chips">
        <label className="chip chip-fixed" title="数字は常に使用されます">
          <input type="checkbox" checked disabled />
          <span>数字</span>
        </label>
        {toggle("upper", "大文字")}
        {toggle("lower", "小文字")}
        {toggle("symbol", "記号")}
      </div>
      <div className="len-row">
        <label>
          最小長
          <input type="number" min={1} max={1024} value={opt.min}
            onChange={(e) => setOpt({ ...opt, min: +e.target.value })} />
        </label>
        <span className="len-sep">〜</span>
        <label>
          最大長
          <input type="number" min={1} max={1024} value={opt.max}
            onChange={(e) => setOpt({ ...opt, max: +e.target.value })} />
        </label>
        <button type="button" className="btn btn-primary" onClick={generate} disabled={busy}>
          <IconRefresh /> 生成
        </button>
      </div>
      <div className={pw ? "gen-out" : "gen-out empty"}>
        <code>{pw || "「生成」をクリックするとここに表示されます"}</code>
        {pw && (
          <>
            <button type="button" className="icon-btn" title="コピー" aria-label="コピー" onClick={copy}>
              <IconCopy />
            </button>
            {actionLabel && onAction && (
              <button type="button" className="btn btn-soft btn-sm" onClick={() => onAction(pw)}>
                <IconCheck /> {actionLabel}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
