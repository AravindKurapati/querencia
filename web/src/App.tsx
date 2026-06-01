import { useSnapshot } from "./data";
import Header from "./components/Header";
import MapHero from "./components/MapHero";
import StatStrip from "./components/StatStrip";
import TasteCard from "./components/TasteCard";
import CountrySection from "./components/CountrySection";
import TimelineSection from "./components/TimelineSection";
import TopPlacesList from "./components/TopPlacesList";
import Footer from "./components/Footer";

export default function App() {
  const { data, error } = useSnapshot();

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="max-w-md text-center">
          <h1 className="font-serif text-3xl mb-4">querencia</h1>
          <p className="text-ink/70 mb-4">No snapshot found.</p>
          <pre className="bg-ink/5 p-3 text-sm text-left rounded font-mono">
            querencia export --out web/public/data.json
          </pre>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center text-ink/50">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header generatedAt={data.generated_at} />
      <MapHero places={data.places} />
      <StatStrip summary={data.summary} />
      <main className="max-w-5xl mx-auto px-6 py-16 space-y-24">
        <TasteCard
          sentence={data.taste_sentence}
          ratingDist={data.rating_dist}
          categories={data.by_category}
        />
        <CountrySection countries={data.by_country} cities={data.by_city} />
        <TimelineSection rows={data.reviews_over_time} />
        <TopPlacesList places={data.places} />
      </main>
      <Footer />
    </div>
  );
}
