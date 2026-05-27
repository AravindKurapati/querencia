export default function Header({ generatedAt }: { generatedAt: string }) {
  const date = new Date(generatedAt).toLocaleDateString(undefined, {
    year: "numeric", month: "long", day: "numeric",
  });
  return (
    <header className="border-b border-rule">
      <div className="max-w-5xl mx-auto px-6 py-5 flex items-baseline justify-between">
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-2xl font-semibold tracking-tight">querencia</h1>
          <span className="text-xs uppercase tracking-widest text-ink/50">
            a place knowledge graph
          </span>
        </div>
        <span className="text-xs text-ink/50">snapshot {date}</span>
      </div>
    </header>
  );
}
