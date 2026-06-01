import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { PlaceMarker } from "../types";

const CATEGORY_COLORS: Record<string, string> = {
  restaurant: "#b4513a",
  cafe: "#c98a4b",
  bar: "#7a4d8a",
  bakery: "#d4a05a",
  park: "#3a7a52",
  food: "#b4513a",
};

export default function MapHero({ places }: { places: PlaceMarker[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: [10, 30],
      zoom: 1.4,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      if (places.length === 0) return;
      const bounds = new maplibregl.LngLatBounds();
      places.forEach((p) => {
        const color = CATEGORY_COLORS[p.category || ""] || "#1a1a1a";
        const el = document.createElement("div");
        el.className = "rounded-full border border-white shadow";
        const size = 8 + Math.min(p.review_count, 5) * 2;
        el.style.width = `${size}px`;
        el.style.height = `${size}px`;
        el.style.background = color;
        new maplibregl.Marker({ element: el })
          .setLngLat([p.lng, p.lat])
          .setPopup(
            new maplibregl.Popup({ offset: 10, closeButton: false }).setHTML(
              `<div style="font-family:Inter,sans-serif;font-size:13px;line-height:1.4;max-width:220px">
                <div style="font-weight:600">${escapeHtml(p.name || "")}</div>
                <div style="color:#666;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-top:2px">
                  ${escapeHtml(p.category || "")} . ${escapeHtml(p.country_code || "")} . ${p.avg_rating}★
                </div>
                <div style="margin-top:6px;color:#333">${escapeHtml(p.sample_text)}</div>
              </div>`
            )
          )
          .addTo(map);
        bounds.extend([p.lng, p.lat]);
      });
      map.fitBounds(bounds, { padding: 60, maxZoom: 6, duration: 0 });
    });

    return () => { map.remove(); mapRef.current = null; };
  }, [places]);

  return (
    <section className="relative">
      <div ref={ref} className="w-full h-[60vh] min-h-[420px] bg-ink/5" />
    </section>
  );
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]!));
}
