import { Search, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/utils/cn";

import type { ImportFieldDefinition, ImportFieldMainType } from "./importFieldSchema";

interface ImportFieldAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  fields: ImportFieldDefinition[];
  mainType?: ImportFieldMainType;
  placeholder?: string;
  disabled?: boolean;
  error?: string | null;
}

export const ImportFieldAutocomplete = ({
  value,
  onChange,
  fields,
  mainType,
  placeholder,
  disabled,
  error,
}: ImportFieldAutocompleteProps) => {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const selectedField = useMemo(
    () => fields.find((field) => field.path === value) || null,
    [fields, value],
  );
  const [query, setQuery] = useState(selectedField?.labelFr || "");
  const [open, setOpen] = useState(false);

  const resetToSelection = useCallback(() => {
    setQuery(selectedField?.labelFr || "");
  }, [selectedField]);

  useEffect(() => {
    setQuery(selectedField?.labelFr || "");
  }, [selectedField]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        resetToSelection();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [resetToSelection]);

  const scopedFields = useMemo(
    () => (mainType ? fields.filter((field) => field.mainType === mainType) : fields),
    [fields, mainType],
  );

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return scopedFields;
    return scopedFields.filter((field) =>
      [field.labelFr, field.path, field.sectionFr, field.type].some((valueToMatch) =>
        valueToMatch.toLowerCase().includes(normalized),
      ),
    );
  }, [query, scopedFields]);

  const grouped = useMemo(() => {
    const map = new Map<string, ImportFieldDefinition[]>();
    for (const field of filtered) {
      const current = map.get(field.sectionFr) || [];
      current.push(field);
      map.set(field.sectionFr, current);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const commitValue = (nextField: ImportFieldDefinition | null) => {
    setQuery(nextField?.labelFr || "");
    onChange(nextField?.path || "");
    setOpen(false);
  };

  return (
    <div ref={rootRef} className="relative">
      <div
        className={cn(
          "flex min-h-[3.25rem] items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50/80 px-3 py-2.5 transition-all",
          "focus-within:border-[#0085A3]/40 focus-within:bg-white focus-within:ring-4 focus-within:ring-[#0085A3]/10",
          error ? "border-rose-300" : "",
          disabled ? "cursor-not-allowed opacity-70" : "",
        )}
      >
        <Search className="h-4 w-4 shrink-0 text-slate-400" />
        <input
          value={query}
          disabled={disabled}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm font-semibold text-slate-800 outline-none placeholder:text-slate-400"
          onFocus={() => setOpen(true)}
          onBlur={() => {
            window.setTimeout(() => {
              resetToSelection();
            }, 100);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && filtered[0]) {
              event.preventDefault();
              commitValue(filtered[0]);
            }
            if (event.key === "Escape") {
              setOpen(false);
              resetToSelection();
            }
          }}
        />
        {query ? (
          <button
            type="button"
            className="rounded-full p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            onClick={() => commitValue(null)}
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {error ? <p className="mt-1 text-[11px] font-medium text-rose-600">{error}</p> : null}

      {open ? (
        <div className="absolute z-30 mt-2 max-h-96 w-full overflow-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl shadow-slate-200/70">
          <button
            type="button"
            className="mb-2 flex w-full items-start rounded-xl px-3 py-2 text-left transition hover:bg-slate-50"
            onClick={() => commitValue(null)}
          >
            <div>
              <p className="text-sm font-bold text-slate-900">Ne pas mapper</p>
              <p className="text-xs text-slate-500">Aucun champ cible</p>
            </div>
          </button>

          {grouped.length ? (
            grouped.map(([group, groupFields]) => (
              <div key={group} className="mb-2 last:mb-0">
                <div className="px-3 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">
                  {group}
                </div>
                <div className="space-y-1">
                  {groupFields.map((field) => (
                    <button
                      key={field.key}
                      type="button"
                      className="flex w-full flex-col items-start rounded-xl px-3 py-2 text-left transition hover:bg-[#0085A3]/5"
                      onClick={() => commitValue(field)}
                    >
                      <div className="flex w-full items-center justify-between gap-3">
                        <span className="text-sm font-bold text-slate-900">{field.labelFr}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold uppercase text-slate-500">
                          {field.type}
                        </span>
                      </div>
                      <div className="mt-1 space-y-0.5 text-xs font-medium text-slate-500">
                        <div>{field.sectionFr}</div>
                        <div className="text-slate-400">{field.path}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <div className="px-3 py-4 text-sm text-slate-500">Aucun champ correspondant.</div>
          )}
        </div>
      ) : null}
    </div>
  );
};
