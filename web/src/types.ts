export interface PlaceMarker {
  place_key: string;
  name: string | null;
  category: string | null;
  country_code: string | null;
  lat: number;
  lng: number;
  review_count: number;
  avg_rating: number;
  sample_text: string;
}

export interface CountryRow { country_code: string; count: number; avg_rating: number; }
export interface CategoryRow { category: string; count: number; avg_rating: number; }
export interface CityRow { city: string; count: number; avg_rating: number; }
export interface TimelineRow { month: string; count: number; }

export interface Snapshot {
  generated_at: string;
  summary: {
    place_count: number;
    review_count: number;
    photo_count: number;
    country_count: number;
    avg_rating: number;
    first_review_at: string | null;
    last_review_at: string | null;
  };
  places: PlaceMarker[];
  by_country: CountryRow[];
  by_category: CategoryRow[];
  by_city: CityRow[];
  rating_dist: Record<string, number>;
  reviews_over_time: TimelineRow[];
  taste_sentence: string;
}
