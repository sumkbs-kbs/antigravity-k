import pytest
from antigravity_k.engine.embeddings import EmbeddingEngine, get_embedding_engine

def test_embedding_engine_initialization():
    engine = EmbeddingEngine()
    assert engine.current_model is None
    assert engine.model is None
    assert engine.tokenizer is None

def test_get_embedding_engine_singleton():
    engine1 = get_embedding_engine()
    engine2 = get_embedding_engine()
    assert engine1 is engine2

def test_load_model():
    engine = EmbeddingEngine()
    model_name = "test-embed-model"
    engine.load_model(model_name)
    assert engine.current_model == model_name

def test_embed_single_string():
    engine = EmbeddingEngine()
    model_name = "test-embed-model"
    text = "Hello world"
    
    embeddings = engine.embed(text, model_name)
    
    assert isinstance(embeddings, list)
    assert len(embeddings) == 1
    assert isinstance(embeddings[0], list)
    assert len(embeddings[0]) == 1536  # Current dummy length

def test_embed_multiple_strings():
    engine = EmbeddingEngine()
    model_name = "test-embed-model"
    texts = ["Hello world", "Test sentence"]
    
    embeddings = engine.embed(texts, model_name)
    
    assert isinstance(embeddings, list)
    assert len(embeddings) == 2
    assert isinstance(embeddings[0], list)
    assert isinstance(embeddings[1], list)
    assert len(embeddings[0]) == 1536
    assert len(embeddings[1]) == 1536
