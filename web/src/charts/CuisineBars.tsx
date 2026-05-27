import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { CategoryRow } from "../types";

export default function CuisineBars({ data }: { data: CategoryRow[] }) {
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical"
                  margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="category" tickLine={false} axisLine={false}
                 tick={{ fontSize: 12, fill: "#1a1a1a" }} width={90} />
          <Tooltip cursor={{ fill: "#1a1a1a10" }}
                   contentStyle={{ fontSize: 12, border: "1px solid #e4e0d6" }} />
          <Bar dataKey="count" fill="#b4513a" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
