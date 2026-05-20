from dataclasses import dataclass, field


@dataclass
class Place:
    place_key: str
    lat: float | None = None
    lng: float | None = None
    canonical_name: str | None = None
    category: str | None = None
    address: str | None = None
    country_code: str | None = None
    source_flags: set[str] = field(default_factory=set)
    enriched_at: str | None = None


@dataclass
class Review:
    place_key: str
    rating: int | None = None
    text: str | None = None
    reviewed_at: str | None = None
    structured_qa: str | None = None  # JSON string


@dataclass
class Photo:
    place_key: str | None
    taken_at: str
    lat: float
    lng: float
    media_type: str


@dataclass
class Visit:
    place_key: str
    occurred_at: str | None
    source: str  # "photo" | "question" | "commute"
    session_id: str | None = None


@dataclass
class Transition:
    from_place_key: str
    to_place_key: str
    travel_mode: str
