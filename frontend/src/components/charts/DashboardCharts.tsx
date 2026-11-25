import {
  Bar,
  BarChart,
  CartesianGrid,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/common/Card";

export const MetricBarChart = ({
  title,
  data,
  dataKey,
  xKey,
}: {
  title: string;
  data: Array<Record<string, string | number>>;
  dataKey: string;
  xKey: string;
}) => (
  <Card className="h-80">
    <h3 className="mb-4 text-lg font-semibold text-ink-900">{title}</h3>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey={dataKey} fill="#22a77f" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  </Card>
);

export const MetricPieChart = ({
  title,
  data,
}: {
  title: string;
  data: Array<{ name: string; value: number; fill: string }>;
}) => (
  <Card className="h-80">
    <h3 className="mb-4 text-lg font-semibold text-ink-900">{title}</h3>
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" outerRadius={100} />
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  </Card>
);
