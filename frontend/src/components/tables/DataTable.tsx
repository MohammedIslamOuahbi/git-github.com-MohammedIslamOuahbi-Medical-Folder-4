import type { ReactNode } from "react";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { cn } from "@/utils/cn";
import { buildEntityUid } from "@/utils/uid";
import { translateUiText } from "@/utils/uiText";

export interface Column<T> {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
  className?: string;
}

export const DataTable = <T,>({
  columns,
  data,
  loading,
  emptyTitle,
  emptyDescription,
  uidScope,
  frame = "card",
  className,
}: {
  columns: Array<Column<T>>;
  data: T[];
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  uidScope?: string;
  frame?: "card" | "plain";
  className?: string;
}) => {
  const tableContent = (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-ink-100">
        <thead className="bg-ink-50">
          <tr>
            {uidScope ? (
              <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500">
                UID
              </th>
            ) : null}
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "px-6 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-ink-500",
                  column.className,
                )}
              >
                {translateUiText(column.title)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100 bg-white">
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-6 py-16 text-center">
                <div className="flex justify-center">
                  <Spinner />
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="p-6">
                <EmptyState
                  title={translateUiText(emptyTitle || "No data found")}
                  description={translateUiText(emptyDescription || "Try adjusting your filters or adding a new record.")}
                />
              </td>
            </tr>
          ) : (
            data.map((row, index) => (
              <tr key={index} className="hover:bg-ink-50/60">
                {uidScope ? (
                  <td className="px-6 py-4 text-sm font-semibold text-brand-700">
                    {buildEntityUid(uidScope, (row as { id?: number }).id || index + 1)}
                  </td>
                ) : null}
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn("px-6 py-4 text-sm text-ink-700", column.className)}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );

  if (frame === "plain") {
    return <div className={cn("overflow-hidden", className)}>{tableContent}</div>;
  }

  return <Card className={cn("overflow-hidden p-0", className)}>{tableContent}</Card>;
};
