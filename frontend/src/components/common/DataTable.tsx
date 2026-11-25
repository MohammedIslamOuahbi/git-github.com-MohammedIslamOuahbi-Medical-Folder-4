import type { ReactNode } from "react";
import { cn } from "@/utils/cn";
import { buildEntityUid } from "@/utils/uid";
import { translateUiText } from "@/utils/uiText";

interface Column<T> {
  key: string;
  title: string;
  className?: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T, index: number) => string | number;
  emptyState?: ReactNode;
  className?: string;
  uidScope?: string;
}

export const DataTable = <T,>({
  columns,
  rows,
  getRowKey,
  emptyState,
  className,
  uidScope,
}: DataTableProps<T>) => (
  <div
    className={cn(
      "overflow-hidden rounded-xl border border-slate-200 bg-white shadow-soft",
      className,
    )}
  >
    <div className="overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-0">
        <thead>
          <tr className="bg-slate-50">
            {uidScope ? (
              <th className="border-b border-slate-200 px-5 py-3.5 text-left text-[10px] font-extrabold uppercase tracking-[0.16em] text-slate-500">
                UID
              </th>
            ) : null}

            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "border-b border-slate-200 px-5 py-3.5 text-left text-[10px] font-extrabold uppercase tracking-[0.16em] text-slate-500",
                  column.className,
                )}
              >
                {translateUiText(column.title)}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows.length > 0 ? (
            rows.map((row, index) => (
              <tr
                key={getRowKey(row, index)}
                className="group transition-colors duration-150 hover:bg-slate-50"
              >
                {uidScope ? (
                  <td className="border-b border-slate-100 px-5 py-4 align-middle">
                    <span className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 font-mono text-[11px] font-medium text-slate-700">
                      {buildEntityUid(
                        uidScope,
                        (row as { id?: number }).id || index + 1,
                      )}
                    </span>
                  </td>
                ) : null}

                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      "border-b border-slate-100 px-5 py-3.5 align-middle text-sm font-medium text-slate-700 transition-colors group-hover:text-slate-950",
                      column.className,
                    )}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td
                colSpan={columns.length + (uidScope ? 1 : 0)}
                className="px-6 py-16 text-center"
              >
                {emptyState || (
                  <div className="flex flex-col items-center justify-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
                      <svg
                        className="h-6 w-6 text-slate-400"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M3 7h18M3 12h18M3 17h18"
                        />
                      </svg>
                    </div>

                    <p className="mt-4 text-sm font-bold text-slate-700">
                      {translateUiText("No records available")}
                    </p>

                    <p className="mt-1 text-xs text-slate-400">
                      {translateUiText("Records will appear here once data is added.")}
                    </p>
                  </div>
                )}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  </div>
);
