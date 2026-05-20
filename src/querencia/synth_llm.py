import json
import os

MODEL = "claude-sonnet-4-6"


def make_client(api_key: str | None = None):
    import anthropic
    return anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])


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
