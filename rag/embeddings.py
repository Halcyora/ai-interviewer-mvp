import json
from typing import List
from config.settings import settings
from config.aws import get_bedrock_runtime


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch embed via AWS Titan Embeddings v2. Returns 1024-dim vectors."""
    client = get_bedrock_runtime()
    embeddings = []
    for text in texts:
        body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
        response = client.invoke_model(
            modelId=settings.bedrock_embed_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        embeddings.append(result["embedding"])
    return embeddings


def embed_single(text: str) -> List[float]:
    return embed_texts([text])[0]
