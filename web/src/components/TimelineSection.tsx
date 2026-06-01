import type { TimelineRow } from "../types";
import TimelineLine from "../charts/TimelineLine";

export default function TimelineSection({ rows }: { rows: TimelineRow[] }) {
  return (
    <section>
      <h2 className="font-serif text-sm uppercase tracking-widest text-ink/50 mb-6">
        Reviews over time
      </h2>
      <TimelineLine data={rows} />
    </section>
  );
}
