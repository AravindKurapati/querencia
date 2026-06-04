import json

MODEL = "claude-sonnet-4-6"


def make_client(api_key: str | None = None):
    from ._keys import require_env_key
    key = require_env_key("ANTHROPIC_API_KEY", api_key)
    import anthropic
    return anthropic.Anthropic(api_key=key)


def render_prose(client, instruction: str, payload: dict) -> str:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                f"{instruction}\n\nGround your answer ONLY in this data; "
                f"do not invent places or facts:\n{json.dumps(payload, indent=2)}"
            ),
        }],
    )
    return msg.content[0].text
