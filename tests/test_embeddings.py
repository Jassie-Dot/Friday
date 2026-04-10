from memory.embeddings import HashEmbeddingProvider


def test_hash_embeddings_are_deterministic():
    provider = HashEmbeddingProvider(dimensions=32)
    first = provider.embed(["friday local assistant"])[0]
    second = provider.embed(["friday local assistant"])[0]
    assert first == second


def test_hash_embeddings_have_expected_dimensions():
    provider = HashEmbeddingProvider(dimensions=32)
    vector = provider.embed(["friday"])[0]
    assert len(vector) == 32
