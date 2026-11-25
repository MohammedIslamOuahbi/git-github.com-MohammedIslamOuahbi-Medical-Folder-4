import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { cn } from "@/utils/cn";

type EditableColumn<T> = {
  key: keyof T;
  title: string;
  type?: "text" | "date";
  placeholder?: string;
  className?: string;
};

interface EditableMedicalTableProps<T extends { id: string }> {
  title: string;
  description?: string;
  columns: EditableColumn<T>[];
  rows: T[];
  createRow: () => T;
  onChange: (rows: T[]) => void;
}

export const EditableMedicalTable = <T extends { id: string }>({
  title,
  description,
  columns,
  rows,
  createRow,
  onChange,
}: EditableMedicalTableProps<T>) => {
  const updateRow = <K extends keyof T>(rowId: string, key: K, value: T[K]) => {
    onChange(rows.map((row) => (row.id === rowId ? { ...row, [key]: value } : row)));
  };

  const removeRow = (rowId: string) => {
    onChange(rows.filter((row) => row.id !== rowId));
  };

  const addRow = () => {
    onChange([...rows, createRow()]);
  };

  return (
    <Card className="overflow-hidden rounded-3xl border border-slate-200 bg-white p-0 shadow-sm">
      <div className="flex flex-col gap-4 border-b border-slate-200 bg-slate-50/60 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-black text-slate-950">{title}</h3>

          {description ? (
            <p className="mt-1 max-w-2xl text-sm text-slate-500">
              {description}
            </p>
          ) : null}
        </div>

        <Button variant="secondary" size="sm" icon={Plus} onClick={addRow}>
          Ajouter
        </Button>
      </div>

      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-slate-200 bg-white">
                {columns.map((column) => (
                  <th
                    key={String(column.key)}
                    className={cn(
                      "px-4 py-3 text-left text-xs font-bold uppercase tracking-wide text-slate-500",
                      column.className,
                    )}
                  >
                    {column.title}
                  </th>
                ))}

                <th className="w-20 px-4 py-3 text-right text-xs font-bold uppercase tracking-wide text-slate-500">
                  Action
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id} className="transition hover:bg-slate-50/70">
                  {columns.map((column) => (
                    <td
                      key={`${row.id}-${String(column.key)}`}
                      className="px-3 py-3"
                    >
                      <input
                        type={column.type || "text"}
                        value={String(row[column.key] || "")}
                        placeholder={column.placeholder}
                        onChange={(event) =>
                          updateRow(
                            row.id,
                            column.key,
                            event.target.value as T[keyof T],
                          )
                        }
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                      />
                    </td>
                  ))}

                  <td className="px-3 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => removeRow(row.id)}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                      aria-label="Supprimer la ligne"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-5 py-8">
          <EmptyState
            title={`Aucune entrée`}
            description="Ajoutez une première ligne pour compléter cette section du dossier."
            actionLabel="Ajouter"
            onAction={addRow}
          />
        </div>
      )}
    </Card>
  );
};