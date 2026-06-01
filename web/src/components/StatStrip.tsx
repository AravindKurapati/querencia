import type { Snapshot } from "../types";

export default function StatStrip({ summary }: { summary: Snapshot["summary"] }) {
  const items = [
    { label: "places", value: summary.place_count },
    { label: "reviews", value: summary.review_count },
    { label: "countries", value: summary.country_count },
    { label: "avg rating", value: summary.avg_rating.toFixed(2) },
  ];
  return (
    <div className="border-y border-rule bg-paper/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-5xl mx-auto px-6 py-5 grid grid-cols-2 md:grid-cols-4 gap-6">
        {items.map((it) => (
          <div key={it.label}>
            <div className="font-serif text-3xl font-semibold leading-none">{it.value}</div>
            <div className="text-xs uppercase tracking-widest text-ink/50 mt-1">{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
