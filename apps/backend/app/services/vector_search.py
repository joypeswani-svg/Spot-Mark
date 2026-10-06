"""
services/vector_search.py — Vector Similarity Search via pgvector

Computes 384-dimensional embeddings locally using sentence-transformers (all-MiniLM-L6-v2)
and performs nearest-neighbor vector search in PostgreSQL (pgvector extension)
against a curated corpus of fact-checked claims (Snopes, PolitiFact, Reuters, AP, BOOM, AltNews, PIB).
"""

import logging
from typing import List, Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger("truthlens.vector_search")

# Model singleton
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local embedding model: {settings.EMBEDDING_MODEL}")
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(f"Could not load sentence-transformers model: {e}")
            _model = False
    return _model if _model is not False else None


def compute_embedding(text: str) -> Optional[List[float]]:
    """Compute 384-dim dense vector embedding for input text."""
    model = get_embedding_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, convert_to_numpy=True)
        return vec.tolist()
    except Exception as e:
        logger.warning(f"Embedding computation failed: {e}")
        return None


# Sample curated fact-check corpus for database seeding
SAMPLE_CORPUS = [
    {
        "claim_text": "Pope Francis surprised the world by endorsing Donald Trump for President.",
        "verdict": "FALSE",
        "explanation": "Originates from a known satire website (WTOE 5 News). The Vatican issued a statement confirming no endorsement occurred.",
        "source_name": "Snopes",
        "source_url": "https://www.snopes.com/fact-check/pope-francis-donald-trump-endorsement/"
    },
    {
        "claim_text": "Drinking warm lemon water cures cancer and destroys malignant cells 10,000 times stronger than chemotherapy.",
        "verdict": "FALSE",
        "explanation": "No scientific evidence supports lemon water as a cure for cancer. Chemotherapy remains an established evidence-based treatment.",
        "source_name": "Reuters Fact Check",
        "source_url": "https://www.reuters.com/article/factcheck-lemon-cancer/"
    },
    {
        "claim_text": "NASA confirmed that Earth will experience 3 days of total darkness in December due to a solar storm.",
        "verdict": "FALSE",
        "explanation": "NASA has debunked this recurring hoax multiple times. No blackout event is expected or scientifically possible.",
        "source_name": "PolitiFact",
        "source_url": "https://www.politifact.com/factchecks/2014/nov/04/blog-posting/hoax-claims-nasa-predicts-total-darkness/"
    },
    {
        "claim_text": "Government announced a monthly allowance of Rs 5,000 to all unemployed youth under a new central scheme.",
        "verdict": "FALSE",
        "explanation": "PIB Fact Check clarified that no such scheme has been launched by the Indian government. The viral message is fraudulent.",
        "source_name": "PIB Fact Check",
        "source_url": "https://factcheck.pib.gov.in/"
    },
    {
        "claim_text": "UNESCO has named the Indian National Anthem as the Best National Anthem in the World.",
        "verdict": "FALSE",
        "explanation": "UNESCO never declared any national anthem as best in the world. This is a long-standing viral chain email hoax.",
        "source_name": "BOOM Live",
        "source_url": "https://www.boomlive.in/fact-check/unesco-best-national-anthem-hoax/"
    }
]


async def seed_corpus_if_empty(session: AsyncSession):
    """Seed sample fact-checked claims into postgres pgvector if empty."""
    try:
        result = await session.execute(sa.text("SELECT COUNT(*) FROM corpus_embeddings;"))
        count = result.scalar()
        if count == 0:
            logger.info("Seeding initial fact-check corpus into pgvector...")
            for item in SAMPLE_CORPUS:
                vec = compute_embedding(item["claim_text"])
                vec_str = str(vec) if vec else None
                await session.execute(
                    sa.text("""
                        INSERT INTO corpus_embeddings (id, claim_text, verdict, explanation, source_name, source_url, embedding)
                        VALUES (uuid_generate_v4(), :claim, :verdict, :exp, :s_name, :s_url, :vec::vector);
                    """),
                    {
                        "claim": item["claim_text"],
                        "verdict": item["verdict"],
                        "exp": item["explanation"],
                        "s_name": item["source_name"],
                        "s_url": item["source_url"],
                        "vec": vec_str
                    }
                )
            await session.commit()
            logger.info("Corpus seeding completed.")
    except Exception as e:
        logger.warning(f"Corpus seeding skipped or failed: {e}")


async def search_vector_corpus(claim_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Perform pgvector similarity search against fact-checked corpus in Postgres.
    """
    embedding = compute_embedding(claim_text)
    if not embedding:
        return []

    try:
        # Fast connect timeout (1.5s) so if Docker/Postgres is offline, API calls don't hang
        engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args={"timeout": 1.5}
        )
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            await seed_corpus_if_empty(session)

            vec_str = str(embedding)
            # pgvector cosine distance operator <=>
            query = sa.text("""
                SELECT claim_text, verdict, explanation, source_name, source_url,
                       1 - (embedding <=> :vec::vector) AS similarity
                FROM corpus_embeddings
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :vec::vector ASC
                LIMIT :limit;
            """)

            result = await session.execute(query, {"vec": vec_str, "limit": top_k})
            rows = result.fetchall()

            matches = []
            for row in rows:
                if row.similarity >= 0.55:  # Similarity threshold
                    matches.append({
                        "claimText": row.claim_text,
                        "verdict": row.verdict,
                        "explanation": row.explanation,
                        "sourceName": row.source_name,
                        "sourceUrl": row.source_url,
                        "similarity": round(float(row.similarity), 3)
                    })

            await engine.dispose()
            return matches
    except Exception as e:
        logger.warning(f"Vector search failed (DB might be offline/unreachable): {e}")
        return []
