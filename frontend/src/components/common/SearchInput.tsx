import { Search } from "lucide-react";
import { translateUiText } from "@/utils/uiText";

export const SearchInput = ({
  value,
  onChange,
  placeholder = "Search...",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) => (
  <div className="flex items-center gap-2.5 rounded-md border border-slate-200 bg-white px-3 py-2 shadow-sm transition-colors duration-150 focus-within:border-blue-600 focus-within:ring-4 focus-within:ring-blue-600/10">
    <Search className="h-4 w-4 text-slate-400" />
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={translateUiText(placeholder)}
      className="w-full bg-transparent text-sm text-ink-800 outline-none placeholder:text-slate-400"
    />
  </div>
);
