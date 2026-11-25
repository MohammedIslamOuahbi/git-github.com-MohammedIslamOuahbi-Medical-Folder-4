import { useEffect, useId, useMemo, useRef, useState } from "react";
import { AlertCircle, Loader2, Search, X } from "lucide-react";
import type { MedicineSearchItem } from "@/types/medicine";
import { cn } from "@/utils/cn";
import { searchMedicines } from "@/services/medicineApi";

type MedicineAutocompleteProps = {
  value: string;
  selectedMedicineId?: number | null;
  onChange: (value: string) => void;
  onSelect: (item: MedicineSearchItem) => void;
  onClear: () => void;
  onManualEntryStateChange?: (isManualEntry: boolean) => void;
  disabled?: boolean;
  placeholder?: string;
  error?: string | null;
};

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 300;
const BLUR_CLOSE_DELAY_MS = 160;

const queryCache = new Map<string, MedicineSearchItem[]>();

const highlight = (text: string, query: string) => {
  const trimmed = query.trim();
  if (!trimmed) return text;
  const lowerText = text.toLowerCase();
  const lowerQuery = trimmed.toLowerCase();
  const start = lowerText.indexOf(lowerQuery);
  if (start === -1) return text;
  const end = start + trimmed.length;
  return (
    <>
      <span>{text.slice(0, start)}</span>
      <mark className="rounded bg-cyan-100 px-0.5 text-slate-950">{text.slice(start, end)}</mark>
      <span>{text.slice(end)}</span>
    </>
  );
};

const normalizeSearchResponse = (payload: unknown): { items: MedicineSearchItem[]; total: number } => {
  if (Array.isArray(payload)) {
    return {
      items: payload as MedicineSearchItem[],
      total: payload.length,
    };
  }

  if (payload && typeof payload === "object" && "items" in payload) {
    const response = payload as { items?: unknown; total?: unknown };
    const items = Array.isArray(response.items)
      ? ((response.items as MedicineSearchItem[]) ?? [])
      : [];
    const total = typeof response.total === "number" ? response.total : items.length;
    return { items, total };
  }

  return { items: [], total: 0 };
};

export const MedicineAutocomplete = ({
  value,
  selectedMedicineId = null,
  onChange,
  onSelect,
  onClear,
  onManualEntryStateChange,
  disabled,
  placeholder = "Rechercher un medicament...",
  error,
}: MedicineAutocompleteProps) => {
  const inputId = useId();
  const listboxId = `${inputId}-listbox`;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const blurTimeoutRef = useRef<number | null>(null);

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<MedicineSearchItem[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [hasSearched, setHasSearched] = useState(false);
  const [userFinishedEditing, setUserFinishedEditing] = useState(false);

  const trimmedValue = value.trim();
  const hasEnoughCharacters = trimmedValue.length >= MIN_QUERY_LENGTH;
  const helperMessage = useMemo(() => {
    if (!trimmedValue || trimmedValue.length < MIN_QUERY_LENGTH) return "Saisissez au moins 2 caracteres.";
    if (isLoading) return "Chargement...";
    if (searchError) return "Erreur lors de la recherche des medicaments.";
    if (!results.length) return "Aucun medicament trouve.";
    return null;
  }, [isLoading, results.length, searchError, trimmedValue]);

  const isManualEntry =
    trimmedValue.length > 0 &&
    selectedMedicineId === null &&
    hasSearched &&
    !isLoading &&
    !isDropdownOpen &&
    userFinishedEditing;

  useEffect(() => {
    onManualEntryStateChange?.(isManualEntry);
  }, [isManualEntry, onManualEntryStateChange]);

  useEffect(() => {
    if (disabled) {
      setIsDropdownOpen(false);
      return;
    }

    if (!hasEnoughCharacters) {
      requestRef.current?.abort();
      setIsLoading(false);
      setResults([]);
      setSearchError(null);
      setActiveIndex(-1);
      setHasSearched(false);
      return;
    }

    const normalizedKey = trimmedValue.toLowerCase();
    if (queryCache.has(normalizedKey)) {
      const cachedResults = queryCache.get(normalizedKey) || [];
      setResults(cachedResults);
      setIsDropdownOpen(true);
      setIsLoading(false);
      setSearchError(null);
      setActiveIndex(cachedResults.length ? 0 : -1);
      setHasSearched(true);
      return;
    }

    setIsLoading(true);
    setSearchError(null);
    setIsDropdownOpen(true);

    const timer = window.setTimeout(() => {
      requestRef.current?.abort();
      const controller = new AbortController();
      requestRef.current = controller;

      void searchMedicines(trimmedValue, {
        limit: 20,
        activeOnly: true,
        signal: controller.signal,
      })
        .then((response) => {
          const normalized = normalizeSearchResponse(response);
          queryCache.set(normalizedKey, normalized.items);
          setResults(normalized.items);
          setSearchError(null);
          setIsDropdownOpen(true);
          setActiveIndex(normalized.items.length ? 0 : -1);
          setHasSearched(true);
        })
        .catch((caught: unknown) => {
          if (controller.signal.aborted) return;
          console.error("[MedicineAutocomplete] search failed", {
            query: trimmedValue,
            error: caught,
          });
          setResults([]);
          setSearchError("search_failed");
          setIsDropdownOpen(true);
          setActiveIndex(-1);
          setHasSearched(true);
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [disabled, hasEnoughCharacters, trimmedValue]);

  useEffect(() => {
    return () => {
      requestRef.current?.abort();
      if (blurTimeoutRef.current) {
        window.clearTimeout(blurTimeoutRef.current);
      }
    };
  }, []);

  const handleSelect = (item: MedicineSearchItem) => {
    setUserFinishedEditing(false);
    onSelect(item);
    setIsDropdownOpen(false);
    setResults([]);
    setSearchError(null);
    setActiveIndex(-1);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isDropdownOpen && event.key === "ArrowDown" && results.length) {
      setIsDropdownOpen(true);
      setActiveIndex(0);
      return;
    }

    if (!isDropdownOpen) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % Math.max(results.length, 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current <= 0 ? results.length - 1 : current - 1));
      return;
    }

    if (event.key === "Enter" && activeIndex >= 0 && results[activeIndex]) {
      event.preventDefault();
      handleSelect(results[activeIndex]);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setIsDropdownOpen(false);
      setUserFinishedEditing(true);
    }
  };

  return (
    <div ref={containerRef} className="relative z-50">
      <label className="block space-y-2">
        <span className="text-sm font-semibold text-navy-800">Medicament</span>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            role="combobox"
            aria-expanded={isDropdownOpen}
            aria-controls={listboxId}
            aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
            value={value}
            disabled={disabled}
            placeholder={placeholder}
            onFocus={() => {
              if (blurTimeoutRef.current) {
                window.clearTimeout(blurTimeoutRef.current);
              }
              setUserFinishedEditing(false);
              if (hasEnoughCharacters) {
                setIsDropdownOpen(true);
              }
            }}
            onBlur={() => {
              blurTimeoutRef.current = window.setTimeout(() => {
                setIsDropdownOpen(false);
                setUserFinishedEditing(true);
              }, BLUR_CLOSE_DELAY_MS);
            }}
            onChange={(event) => {
              setUserFinishedEditing(false);
              onChange(event.target.value);
              if (event.target.value.trim().length >= MIN_QUERY_LENGTH) {
                setIsDropdownOpen(true);
              }
            }}
            onKeyDown={handleKeyDown}
            className={cn(
              "w-full rounded-[0.375rem] border border-slate-200/80 bg-white/[0.72] px-10 py-3 text-sm font-semibold text-ink-800 outline-none backdrop-blur-sm transition-all duration-200 focus:-translate-y-0.5 focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-brand-100/70",
              error && "border-rose-300",
            )}
          />
          {isLoading ? (
            <Loader2 className="absolute right-10 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-slate-400" />
          ) : null}
          {value ? (
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                setUserFinishedEditing(false);
                setIsDropdownOpen(false);
                setResults([]);
                setSearchError(null);
                setHasSearched(false);
                onClear();
              }}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              aria-label="Effacer le medicament"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>
        {error ? <span className="text-[11px] font-medium text-rose-600">{error}</span> : null}
      </label>

      {isDropdownOpen && hasEnoughCharacters ? (
        <div
          id={listboxId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-2 max-h-72 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl"
        >
          {results.length ? (
            results.map((item, index) => (
              <button
                key={`${inputId}-${item.id}`}
                id={`${listboxId}-${index}`}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={cn(
                  "w-full rounded-xl px-3 py-2 text-left transition",
                  index === activeIndex ? "bg-cyan-50" : "hover:bg-slate-50",
                )}
                onMouseDown={(event) => {
                  event.preventDefault();
                  if (blurTimeoutRef.current) {
                    window.clearTimeout(blurTimeoutRef.current);
                  }
                  handleSelect(item);
                }}
              >
                <p className="text-sm font-bold text-slate-900">
                  {highlight([item.brandName, item.strength].filter(Boolean).join(" - "), trimmedValue)}
                </p>
                {item.genericName ? (
                  <p className="mt-1 text-xs font-medium text-slate-600">{highlight(item.genericName, trimmedValue)}</p>
                ) : null}
                <p className="mt-1 text-xs text-slate-500">
                  {[item.pharmaceuticalForm, item.packaging, item.laboratory].filter(Boolean).join(" · ") || "-"}
                </p>
              </button>
            ))
          ) : (
            <div className="flex items-center gap-2 rounded-xl px-3 py-3 text-sm text-slate-500">
              {searchError ? <AlertCircle className="h-4 w-4 text-rose-500" /> : null}
              <span>{helperMessage}</span>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};
