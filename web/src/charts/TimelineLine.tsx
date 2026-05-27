import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import type { TimelineRow } from "../types";

export default function TimelineLine({ data }: { data: TimelineRow[] }) {
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="month" tickLine={false} axisLine={false}
                 tick={{ fontSize: 11, fill: "#1a1a1a80" }} interval="preserveStartEnd" />
          <YAxis tickLine={false} axisLine={false}
                 tick={{ fontSize: 11, fill: "#1a1a1a80" }} width={28} />
          <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e4e0d6" }} />
          <Line type="monotone" dataKey="count" stroke="#b4513a" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
