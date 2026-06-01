# FEATURE: Taste model + cross-city recommender

Delivers the README's headline promise: *"what would I like in a city I've never visited?"*

Today `taste(city)` only lists the user's top categories — it ignores the city argument
entirely. This feature fixes that.

## Why
The unique value of querencia vs. a generic restaurant aggregator is *your* preference
vector applied to *somewhere new*. This is the agentic, ML-ish payoff.

## Approach
Three stages, all local except the candidate fetch:

1. **Preference vector** (LLM-free): weighted average of review-text embeddings, weighted
   by `(rating - avg_rating)` so positive-deviation places dominate. Per-category sub-vectors
   plus a global vector. Cached in a new table; recomputed on demand.

2. **Candidate fetch** (only step touching the internet): Google Places `nearby_search`
   for each top category in the target city center. Cached per `(city, category)` so repeat
   queries don't burn API quota. Falls back gracefully if `GOOGLE_PLACES_API_KEY` unset
   by reading candidates from any place already in the DB whose country matches.

3. **Score + rank** (LLM-free): cosine(candidate_text_embedding, user_pref_vector) +
   category prior weight. Returns top-N with a `because` field listing the 2 nearest
   user-reviewed places (justification).

## Scope
1. `querencia.taste` module (split from `query.py` taste function):
   - `preference_vector(conn, embedder) -> dict[category, np.ndarray]`
   - `fetch_candidates(client, city, categories, *, cache) -> list[dict]`
   - `recommend(conn, embedder, city, *, client=None, top=10) -> list[dict]`

2. Schema additions:
   ```sql
   CREATE TABLE pref_vectors(
     category TEXT PRIMARY KEY,
     vector BLOB,        -- pickled np.ndarray
     n_reviews INTEGER,
     computed_at TIMESTAMP
   );
   CREATE TABLE candidate_cache(
     city TEXT, category TEXT, payload TEXT,
     fetched_at TIMESTAMP,
     PRIMARY KEY (city, category)
   );
   ```

3. CLI: `querencia recommend <city> [--top N] [--json]`. Graceful prose via Anthropic if key set.

4. Tests
   - preference vector weights positive ratings more.
   - mocked Places client → deterministic candidate list → expected ranking.
   - no API key + no in-DB candidates → returns empty with helpful message (no crash).
   - cache hit avoids second API call.

## Out of scope
- Wikidata-based candidate fetch (alternative to Google Places).
- Personalized confidence intervals.
- Multi-city trip planning.

## Risk
Medium. API spend is the real risk. Mitigations: aggressive caching, opt-in via flag,
default `top=5` to bound categories searched, never run on `enrich`-style scale.

## Cost note
Google Places Nearby Search ≈ $32 / 1000 calls. One `recommend <city>` with top 5
categories = 5 calls = ~$0.16. Cache ensures repeat calls cost $0.
