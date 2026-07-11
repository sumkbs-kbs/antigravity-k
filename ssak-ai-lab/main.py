from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class KnowledgeArticle(BaseModel):
    title: str
    content: str
    tags: List[str] = []


articles = []


@app.post("/api/knowledge/")
def create_article(article: KnowledgeArticle):
    articles.append(article)
    return article


@app.get("/api/knowledge/")
def read_articles():
    return articles
