export default function Footer() {
  return (
    <footer className="border-t border-rule mt-16">
      <div className="max-w-5xl mx-auto px-6 py-8 text-xs text-ink/50 flex justify-between">
        <span>built locally from Google Maps contributions . data stays on disk</span>
        <a
          className="hover:text-ink"
          href="https://github.com/AravindKurapati/querencia"
          target="_blank"
          rel="noreferrer"
        >
          github.com/AravindKurapati/querencia
        </a>
      </div>
    </footer>
  );
}
