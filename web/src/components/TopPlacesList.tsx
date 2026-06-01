import type { PlaceMarker } from "../types";

export default function TopPlacesList({ places }: { places: PlaceMarker[] }) {
  const top = [...places]
    .sort((a, b) => b.avg_rating - a.avg_rating || b.review_count - a.review_count)
    .slice(0, 10);
  return (
    <section>
      <h2 className="font-serif text-sm uppercase tracking-widest text-ink/50 mb-6">
        Highest-rated places
      </h2>
      <ol className="space-y-6">
        {top.map((p, i) => (
          <li key={p.place_key} className="grid grid-cols-[2rem_1fr_auto] gap-4 items-baseline border-b border-rule pb-5">
            <span className="font-serif text-2xl text-ink/30 tabular-nums">{i + 1}</span>
            <div>
              <div className="font-serif text-xl">{p.name}</div>
              <div className="text-xs uppercase tracking-widest text-ink/50 mt-1">
                {p.category} . {p.country_code}
              </div>
              {p.sample_text && (
                <p className="mt-2 text-sm text-ink/70 max-w-2xl">{p.sample_text}</p>
              )}
            </div>
            <span className="font-serif text-xl text-accent tabular-nums">
              {p.avg_rating.toFixed(1)}★
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
