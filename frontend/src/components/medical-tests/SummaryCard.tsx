interface SummaryCardProps {
  title: string;
  items: [string, string | number | undefined | null][];
}

export default function SummaryCard({
  title,
  items,
}: SummaryCardProps) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-1">
      {/* Title */}
      <div className="border border-slate-200 bg-white p-2 shadow-sm flex items-center">
        <h4 className="font-semibold text-slate-900">
          {title}
        </h4>
      </div>

      {/* Values */}
      <div className="border border-slate-200 bg-white p-2 shadow-sm">
        <div className="space-y-1 text-slate-700">
        {items.map(([label, value]) => (
          <p key={label}>
            <span className="font-medium text-slate-600">
              {label} :
            </span>{" "}
            <span className="text-slate-900">
              {value || "-"}
            </span>
          </p>
        ))}
      </div>
      </div>
    </div>
  );
}