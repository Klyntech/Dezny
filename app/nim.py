import httpx

from app.config import get_settings


class NIMError(RuntimeError):
    pass


def _headers():
    key = get_settings().nvidia_api_key
    if not key:
        raise NIMError("NVIDIA_API_KEY is not configured")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def embed_texts(texts: list[str], input_type: str = "passage") -> list[list[float]]:
    s = get_settings()
    if not texts:
        return []
    payload = {"model": s.nvidia_embedding_model, "input": texts, "input_type": input_type, "encoding_format": "float"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
        response = await client.post(f"{s.nvidia_nim_base_url.rstrip('/')}/embeddings", headers=_headers(), json=payload)
    if response.is_error:
        raise NIMError(f"NIM embeddings failed ({response.status_code}): {response.text[:400]}")
    rows = sorted(response.json().get("data", []), key=lambda row: row.get("index", 0))
    vectors = [row["embedding"] for row in rows]
    if len(vectors) != len(texts):
        raise NIMError("NIM returned an unexpected number of embeddings")
    if any(len(vector) != s.embedding_dimensions for vector in vectors):
        raise NIMError("Embedding dimension mismatch; update configuration and migration together")
    return vectors


async def chat(messages: list[dict[str, str]]) -> str:
    s = get_settings()
    payload = {"model": s.nvidia_chat_model, "messages": messages, "temperature": 0.1, "max_tokens": 1600}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
        response = await client.post(f"{s.nvidia_nim_base_url.rstrip('/')}/chat/completions", headers=_headers(), json=payload)
    if response.is_error:
        raise NIMError(f"NIM chat failed ({response.status_code}): {response.text[:400]}")
    choices = response.json().get("choices", [])
    if not choices:
        raise NIMError("NIM returned no answer choices")
    return choices[0]["message"]["content"].strip()
