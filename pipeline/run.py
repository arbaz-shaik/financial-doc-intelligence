import hashlib

from pipeline.sec_client import SECClient
from pipeline.news_client import NewsClient
from pipeline.chunker import Chunker
from pipeline.store import ChunkStore
from pipeline.parser import DocumentParser
from src.logger import get_logger
from src.config import settings


logger = get_logger(__name__)


def run_pipeline(companies: list[str]):

        # The API can run without the News API key, so Settings treats it as optional.
    # The pipeline requires it, so validate it here before creating any clients.
    if not settings.news_api_key:
        raise ValueError(
            "NEWS_API_KEY is missing. Set NEWS_API_KEY in your .env file."
        )

    CIK_MAP = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
        "JPM": "0000019617",
        "GOOGL": "0001652044",
    }


    sec_client = SECClient(settings.sec_user_agent)
    parser = DocumentParser()
    news_client = NewsClient(settings.news_api_key)
    chunker = Chunker(chunk_size=512, chunk_overlap=50)
    chunk_store = ChunkStore("data/chunks")

    for company in companies:
        logger.info(f"Processing SEC filing for {company}...")

        cik = CIK_MAP.get(company)
        if not cik:
            logger.error(f"CIK not found for company: {company}")
            continue

        sec_client_results = sec_client.search(CIK=cik)
        if not sec_client_results:
            logger.warning(f"No SEC filings found for {company}")
            continue

        sec_client_filing = sec_client_results[0]

        # Keep date for filtering and doc_id for document identification.
        metadata = {
            "doc_id": sec_client_filing["accessionNumber"],
            "source": "sec",
            "company": company,
            "doc_type": "10-K",
            "date": sec_client_filing["reportDate"],
            "section": None,
        }

        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik.lstrip('0')}/"
            f"{sec_client_filing['accessionNumber'].replace('-', '')}/"
            f"{sec_client_filing['primaryDocument']}"
        )

        sec_client_html = sec_client.download(url)
        sec_client_text = parser.parse_html(sec_client_html)

        chunks = chunker.chunk_text(
            sec_client_text,
            metadata=metadata,
        )

        chunk_store.save_chunks(
            chunks,
            filename=f"{company}-10K-{sec_client_filing['reportDate']}",
        )

        news_client_results = news_client.fetch_news(
            company,
            days_back=10,
        )

        for article in news_client_results:
            # Generate a short fingerprint from the article URL.
            url_hash = hashlib.md5(
                article["url"].encode("utf-8")
            ).hexdigest()[:8]

            metadata = {
                "doc_id": url_hash,
                "source": "news",
                "company": company,
                "doc_type": "news",
                "date": article["date"],
                "section": None,
            }

            chunks = chunker.chunk_text(
                article["text"],
                metadata=metadata,
            )

            chunk_store.save_chunks(
                chunks,
                filename=f"{company}-news-{article['date']}",
            )

        logger.info(
            f"Processing {len(news_client_results)} news articles "
            f"for {company}..."
        )

    logger.info("Pipeline completed.")


if __name__ == "__main__":
    run_pipeline(["AAPL"])

    store = ChunkStore("data/chunks")
    print(store.stats())