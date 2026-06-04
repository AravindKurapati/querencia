"""The local-first credential contract: no/blank key => catchable KeyError.

querencia promises the whole pipeline works offline. That promise rests on the
client constructors raising KeyError (and only KeyError) when no usable key is
configured, so the `except KeyError` fallbacks in cli.py / mcp_server.py select
the offline path instead of crashing. These tests pin that contract -- and they
deliberately run without googlemaps/anthropic installed, proving the no-key path
never even imports the vendor SDK.
"""
import pytest

from querencia._keys import require_env_key

ENV_VARS = ("GOOGLE_PLACES_API_KEY", "ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def _clear_keys(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_require_env_key_returns_value_from_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "abc123")
    assert require_env_key("GOOGLE_PLACES_API_KEY") == "abc123"


def test_require_env_key_strips_surrounding_whitespace(monkeypatch):
    # A trailing newline read into the env var must not corrupt the key.
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "  abc123\n")
    assert require_env_key("GOOGLE_PLACES_API_KEY") == "abc123"


def test_require_env_key_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "from-env")
    assert require_env_key("GOOGLE_PLACES_API_KEY", "explicit") == "explicit"


def test_require_env_key_raises_when_unset():
    with pytest.raises(KeyError):
        require_env_key("GOOGLE_PLACES_API_KEY")


@pytest.mark.parametrize("blank", ["", "   ", "\n", "\t "])
def test_require_env_key_raises_when_blank(monkeypatch, blank):
    # An empty/blank env var is the common .env / CI footgun: it must fall back
    # (KeyError), not slip through to crash inside the vendor SDK.
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", blank)
    with pytest.raises(KeyError):
        require_env_key("GOOGLE_PLACES_API_KEY")


def test_require_env_key_blank_override_raises(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "from-env")
    with pytest.raises(KeyError):
        require_env_key("GOOGLE_PLACES_API_KEY", "  ")


# --- The constructors honor the contract (and don't import the vendor SDK on
#     the no-key path, so these pass even without googlemaps/anthropic). ---

def test_places_client_raises_keyerror_when_unset():
    from querencia.taste import PlacesClient
    with pytest.raises(KeyError):
        PlacesClient()


def test_places_client_raises_keyerror_when_blank(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    from querencia.taste import PlacesClient
    with pytest.raises(KeyError):
        PlacesClient()


def test_google_client_raises_keyerror_when_unset():
    from querencia.enrich import GoogleClient
    with pytest.raises(KeyError):
        GoogleClient()


def test_google_client_raises_keyerror_when_blank(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "   ")
    from querencia.enrich import GoogleClient
    with pytest.raises(KeyError):
        GoogleClient()


def test_make_client_raises_keyerror_when_unset():
    from querencia.synth_llm import make_client
    with pytest.raises(KeyError):
        make_client()


def test_make_client_raises_keyerror_when_blank(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from querencia.synth_llm import make_client
    with pytest.raises(KeyError):
        make_client()
