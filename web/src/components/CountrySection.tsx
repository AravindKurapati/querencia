import type { CountryRow, CityRow } from "../types";

interface Props { countries: CountryRow[]; cities: CityRow[]; }

export default function CountrySection({ countries, cities }: Props) {
  return (
    <section>
      <h2 className="font-serif text-sm uppercase tracking-widest text-ink/50 mb-6">
        Where you've been
      </h2>
      <div className="grid md:grid-cols-2 gap-10">
        <div>
          <h3 className="text-xs uppercase tracking-widest text-ink/50 mb-3">By country</h3>
          <ul className="divide-y divide-rule">
            {countries.map((c) => (
              <li key={c.country_code} className="flex items-baseline justify-between py-2.5">
                <span className="font-serif text-lg">{c.country_code}</span>
                <span className="text-sm text-ink/60">
                  {c.count} {c.count === 1 ? "place" : "places"} . {c.avg_rating}★
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-xs uppercase tracking-widest text-ink/50 mb-3">By city</h3>
          <ul className="divide-y divide-rule">
            {cities.slice(0, 10).map((c) => (
              <li key={c.city} className="flex items-baseline justify-between py-2.5">
                <span className="font-serif text-lg">{c.city}</span>
                <span className="text-sm text-ink/60">
                  {c.count} {c.count === 1 ? "place" : "places"} . {c.avg_rating}★
                </span>
              </li>
            ))}
            {cities.length === 0 && (
              <li className="py-2.5 text-sm text-ink/40">No city data yet.</li>
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
