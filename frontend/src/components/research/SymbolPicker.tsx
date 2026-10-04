import { useEffect, useRef, useState } from "react";

import { searchSymbols } from "../../api";
import type { SymbolMatch } from "../../types";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onPick: (m: SymbolMatch) => void;
  prefer: string;
  disabled: boolean;
}

/** Ticker input with live "closest match" suggestions as the user types. */
export function SymbolPicker({ value, onChange, onPick, prefer, disabled }: Props) {
  const [items, setItems] = useState<SymbolMatch[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [empty, setEmpty] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const skipNext = useRef(false); // do not re-search right after a suggestion was picked

  useEffect(() => {
    if (skipNext.current) { skipNext.current = false; return; }
    const q = value.trim();
    if (q.length < 2) { setItems([]); setOpen(false); setEmpty(false); return; }
    const ctl = new AbortController();
    const t = window.setTimeout(() => {
      setLoading(true);
      searchSymbols(q, prefer, ctl.signal)
        .then((r) => { setItems(r); setEmpty(r.length === 0); setActive(-1); setOpen(true); })
        .catch(() => { /* aborted or offline: keep the typed text usable */ })
        .finally(() => setLoading(false));
    }, 250);
    return () => { window.clearTimeout(t); ctl.abort(); };
  }, [value, prefer]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (!boxRef.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (m: SymbolMatch) => {
    skipNext.current = true;
    setOpen(false);
    onPick(m);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!open || !items.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (a + 1) % items.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (a <= 0 ? items.length - 1 : a - 1)); }
    else if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(items[active]); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="symbol-picker" ref={boxRef}>
      <label>Ticker or company name
        <input value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={onKey}
               onFocus={() => items.length && setOpen(true)} placeholder="Type e.g. tata cons, reliance, apple"
               required disabled={disabled} autoComplete="off" role="combobox" aria-expanded={open}
               aria-autocomplete="list" aria-controls="symbol-list" />
      </label>
      {loading && <i className="spinner mini" aria-label="Searching" />}
      {open && (
        <ul id="symbol-list" className="suggestions" role="listbox">
          {empty && <li className="none">No close matches. Try the company name or the exact Yahoo symbol.</li>}
          {items.map((m, i) => (
            <li key={m.symbol} role="option" aria-selected={i === active} className={i === active ? "active" : ""}
                onMouseDown={(e) => { e.preventDefault(); pick(m); }} onMouseEnter={() => setActive(i)}>
              <b>{m.symbol}</b>
              <span>{m.name}</span>
              <small>{m.exchange}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
