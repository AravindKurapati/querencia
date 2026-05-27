import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

export default function RatingDistBar({ data }: { data: Record<string, number> }) {
  const rows = ["1", "2", "3", "4", "5"].map((k) => ({ rating: `${k}★`, count: data[k] || 0 }));
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
          <XAxis dataKey="rating" tickLine={false} axisLine={false}
                 tick={{ fontSize: 12, fill: "#1a1a1a" }} />
          <YAxis hide />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {rows.map((_, i) => (
              <Cell key={i} fill={i === 4 ? "#b4513a" : "#1a1a1a"} fillOpacity={i === 4 ? 1 : 0.6} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
