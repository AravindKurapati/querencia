import type { CategoryRow } from "../types";
import RatingDistBar from "../charts/RatingDistBar";
import CuisineBars from "../charts/CuisineBars";

interface Props {
  sentence: string;
  ratingDist: Record<string, number>;
  categories: CategoryRow[];
}

export default function TasteCard({ sentence, ratingDist, categories }: Props) {
  return (
    <section>
      <h2 className="font-serif text-sm uppercase tracking-widest text-ink/50 mb-3">
        Your taste, in one sentence
      </h2>
      <p className="font-serif text-2xl md:text-3xl leading-snug max-w-3xl mb-10">
        {sentence}
      </p>
      <div className="grid md:grid-cols-2 gap-10">
        <div>
          <h3 className="text-xs uppercase tracking-widest text-ink/50 mb-3">Rating distribution</h3>
          <RatingDistBar data={ratingDist} />
        </div>
        <div>
          <h3 className="text-xs uppercase tracking-widest text-ink/50 mb-3">Top categories</h3>
          <CuisineBars data={categories.slice(0, 6)} />
        </div>
      </div>
    </section>
  );
}
