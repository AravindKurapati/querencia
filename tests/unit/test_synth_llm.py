from querencia.synth_llm import render_prose


class FakeAnthropic:
    def __init__(self):
        self.messages = self
    def create(self, **kwargs):
        class R:
            content = [type("B", (), {"text": "A lovely food year."})()]
        self.last_kwargs = kwargs
        return R()


def test_render_prose_calls_model_with_payload():
    client = FakeAnthropic()
    out = render_prose(client, "Summarize my food year", {"place_count": 2})
    assert out == "A lovely food year."
    assert "place_count" in str(client.last_kwargs)
