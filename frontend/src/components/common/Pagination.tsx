import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "./Button";
import { translateUiText } from "@/utils/uiText";

export const Pagination = ({
  page,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-soft">
      <div>
        <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-slate-500">
          {translateUiText("Pagination")}
        </p>

        <p className="mt-1 text-sm font-semibold text-slate-700">
          {translateUiText("Page")} <span className="font-extrabold text-blue-700">{page}</span> {translateUiText("of")}{" "}
          <span className="font-black text-slate-950">{totalPages}</span>
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="rounded-lg px-3"
        >
          <ChevronLeft className="h-4 w-4" />
          {translateUiText("Previous")}
        </Button>

        <div className="flex h-8 min-w-[3rem] items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-extrabold text-slate-700">
          {page}
        </div>

        <Button
          variant="secondary"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="rounded-lg px-3"
        >
          {translateUiText("Next")}
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};
