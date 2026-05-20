# Manual demo verification

Prereq: real Takeout extracted, GOOGLE_PLACES_API_KEY and ANTHROPIC_API_KEY set (optional).

1. `locus --db locus.db ingest ~/Downloads/takeout-*.zip` → expect reviews: 80, photos: ~1000
2. `locus --db locus.db enrich` → expect "enriched: N" (N ~80-250)
3. `locus --db locus.db embed` → expect "indexed: N"
4. `locus --db locus.db story --theme food` → read prose; verify every named place is a place you actually reviewed (no hallucinations)
5. `locus --db locus.db ask "my favorite South Indian places"` → top result should be a real high-rated review
6. `locus --db locus.db taste Lisbon` → categories should reflect your real preferences

PASS if steps 4-5 produce grounded, non-hallucinated output.
