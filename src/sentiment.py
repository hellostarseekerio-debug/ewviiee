"""
sentiment.py
~~~~~~~~~~~~
Multi-source sentiment aggregation pipeline.

Sources:
  - Twitter/X: bearer-token search API + VADER + FinBERT
  - Reddit: r/ethereum, r/ethtrader, r/CryptoCurrency via PRAW + VADER
  - News: CryptoPanic API + NewsAPI + FinBERT NLP classification
  - Google Trends: pytrends
  - On-chain / whale alerts (from data_feed)
  - Macro/political news NLP with source authority weights

All scores are normalised to [-1, +1].
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import praw
import structlog
from pytrends.request import TrendReq
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import settings

logger = structlog.get_logger(__name__)

# Lazy FinBERT load (expensive, cached at module level)
_finbert_pipeline = None


def _get_finbert():
    global _finbert_pipeline
    if _finbert_pipeline is None:
        try:
            from transformers import pipeline
            _finbert_pipeline = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                device=-1,  # CPU
                truncation=True,
                max_length=512,
            )
            logger.info("finbert_loaded")
        except Exception as exc:
            logger.warning("finbert_load_failed", error=str(exc))
    return _finbert_pipeline


VADER = SentimentIntensityAnalyzer()

# Source authority weights (1.0 = standard, 2.0 = high authority)
SOURCE_WEIGHTS: Dict[str, float] = {
    "coindesk": 1.8,
    "cointelegraph": 1.6,
    "decrypt": 1.5,
    "theblock": 1.8,
    "bloomberg": 2.0,
    "reuters": 2.0,
    "wsj": 2.0,
    "cnbc": 1.9,
    "sec.gov": 2.0,
    "federalreserve.gov": 2.0,
    "twitter": 1.0,
    "reddit": 0.9,
    "cryptopanic": 1.2,
    "newsapi": 1.1,
}

CRYPTO_KEYWORDS = [
    "ethereum", "eth", "ether", "crypto", "defi", "web3",
    "bitcoin", "btc", "blockchain",
]

SEC_KEYWORDS = ["sec", "securities", "regulation", "enforcement", "lawsuit"]
FED_KEYWORDS = ["federal reserve", "fed", "interest rate", "inflation", "fomc"]
CONGRESS_KEYWORDS = ["congress", "senate", "bill", "legislation", "hearing"]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _clean_text(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#", "", text)
    return text.strip()


def vader_score(text: str) -> float:
    """Returns compound VADER score in [-1, 1]."""
    return VADER.polarity_scores(_clean_text(text))["compound"]


def finbert_score(text: str) -> float:
    """Returns FinBERT score: +1 positive, -1 negative, 0 neutral."""
    model = _get_finbert()
    if model is None:
        return vader_score(text)
    try:
        result = model(_clean_text(text[:512]))[0]
        label = result["label"].lower()
        score = result["score"]
        if label == "positive":
            return score
        elif label == "negative":
            return -score
        return 0.0
    except Exception:
        return vader_score(text)


def combined_sentiment(text: str, use_finbert: bool = True) -> float:
    """Weighted average of VADER (40%) + FinBERT (60%)."""
    v = vader_score(text)
    if use_finbert:
        f = finbert_score(text)
        return 0.4 * v + 0.6 * f
    return v


def _source_weight(source: str) -> float:
    src_lower = source.lower()
    for key, w in SOURCE_WEIGHTS.items():
        if key in src_lower:
            return w
    return 1.0


# ─── Twitter / X ─────────────────────────────────────────────────────────────


class TwitterSentiment:
    API_BASE = "https://api.twitter.com/2"
    QUERIES = [
        "ethereum lang:en -is:retweet",
        "ETH crypto lang:en -is:retweet",
        "#ethereum lang:en -is:retweet",
    ]

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {settings.twitter_bearer_token}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def fetch_recent_tweets(self, max_results: int = 100) -> List[str]:
        if not settings.twitter_bearer_token:
            logger.warning("twitter_no_token")
            return []
        session = await self._get_session()
        texts: List[str] = []
        for query in self.QUERIES[:1]:  # limit to 1 query to save quota
            try:
                async with session.get(
                    f"{self.API_BASE}/tweets/search/recent",
                    params={
                        "query": query,
                        "max_results": min(max_results, 100),
                        "tweet.fields": "text,created_at,public_metrics",
                    },
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        texts.extend(
                            t["text"] for t in data.get("data", [])
                        )
            except Exception as exc:
                logger.warning("twitter_fetch_error", error=str(exc))
        return texts

    async def get_score(self) -> Dict[str, Any]:
        tweets = await self.fetch_recent_tweets(100)
        if not tweets:
            return {"score": 0.0, "count": 0, "source": "twitter"}
        scores = [combined_sentiment(t) for t in tweets]
        return {
            "score": float(np.mean(scores)),
            "count": len(scores),
            "std": float(np.std(scores)),
            "source": "twitter",
        }

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# ─── Reddit ───────────────────────────────────────────────────────────────────


class RedditSentiment:
    SUBREDDITS = ["ethereum", "ethtrader", "CryptoCurrency"]

    def get_score(self, limit_per_sub: int = 50) -> Dict[str, Any]:
        if not (settings.reddit_client_id and settings.reddit_client_secret):
            logger.warning("reddit_no_credentials")
            return {"score": 0.0, "count": 0, "source": "reddit"}

        try:
            reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )
            texts: List[str] = []
            for sub_name in self.SUBREDDITS:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=limit_per_sub):
                    texts.append(post.title + " " + (post.selftext or ""))
            scores = [vader_score(t) for t in texts]
            return {
                "score": float(np.mean(scores)) if scores else 0.0,
                "count": len(scores),
                "source": "reddit",
            }
        except Exception as exc:
            logger.warning("reddit_error", error=str(exc))
            return {"score": 0.0, "count": 0, "source": "reddit"}


# ─── News: CryptoPanic + NewsAPI ─────────────────────────────────────────────


class NewsSentiment:
    CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"
    NEWSAPI_URL = "https://newsapi.org/v2/everything"

    async def _fetch_cryptopanic(self) -> List[Tuple[str, str]]:
        if not settings.cryptopanic_api_key:
            return []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.CRYPTOPANIC_URL,
                    params={
                        "auth_token": settings.cryptopanic_api_key,
                        "currencies": "ETH",
                        "filter": "hot",
                        "public": "true",
                    },
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                results = data.get("results", [])
                return [
                    (r.get("title", ""), r.get("source", {}).get("domain", "cryptopanic"))
                    for r in results
                ]
            except Exception as exc:
                logger.warning("cryptopanic_error", error=str(exc))
                return []

    async def _fetch_newsapi(self) -> List[Tuple[str, str]]:
        if not settings.newsapi_key:
            return []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    self.NEWSAPI_URL,
                    params={
                        "apiKey": settings.newsapi_key,
                        "q": "ethereum OR ETH cryptocurrency",
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 50,
                    },
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                articles = data.get("articles", [])
                return [
                    (
                        (a.get("title", "") + " " + (a.get("description") or "")),
                        a.get("source", {}).get("name", "newsapi"),
                    )
                    for a in articles
                ]
            except Exception as exc:
                logger.warning("newsapi_error", error=str(exc))
                return []

    async def get_score(self) -> Dict[str, Any]:
        cp, na = await asyncio.gather(
            self._fetch_cryptopanic(), self._fetch_newsapi()
        )
        all_articles = cp + na
        if not all_articles:
            return {"score": 0.0, "count": 0, "source": "news"}

        weighted_scores: List[float] = []
        weights: List[float] = []
        for text, source in all_articles:
            s = combined_sentiment(text)
            w = _source_weight(source)
            weighted_scores.append(s * w)
            weights.append(w)

        total_weight = sum(weights)
        score = sum(weighted_scores) / total_weight if total_weight > 0 else 0.0
        return {
            "score": float(score),
            "count": len(all_articles),
            "source": "news",
        }


# ─── Macro / Political NLP ────────────────────────────────────────────────────


class MacroNewsSentiment:
    """
    Monitors SEC statements, Fed minutes, Congressional hearings, G7/G20
    crypto regulation news. Classifies each headline and weights by authority.
    """

    RSS_FEEDS = {
        "sec": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&dateb=&owner=include&count=10&search_text=&output=atom",
        "fed": "https://www.federalreserve.gov/feeds/press_all.xml",
    }
    NEWSAPI_QUERIES = [
        "SEC cryptocurrency regulation",
        "Federal Reserve crypto interest rate",
        "G7 G20 cryptocurrency regulation",
        "Congress crypto bill legislation",
    ]

    async def _fetch_newsapi_macro(self, query: str) -> List[Tuple[str, str]]:
        if not settings.newsapi_key:
            return []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "apiKey": settings.newsapi_key,
                        "q": query,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 10,
                    },
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                return [
                    (
                        (a.get("title", "") + " " + (a.get("description") or "")),
                        a.get("source", {}).get("name", "newsapi"),
                    )
                    for a in data.get("articles", [])
                ]
            except Exception:
                return []

    async def get_score(self) -> Dict[str, Any]:
        all_results: List[Tuple[str, str]] = []
        tasks = [self._fetch_newsapi_macro(q) for q in self.NEWSAPI_QUERIES]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for g in gathered:
            if isinstance(g, list):
                all_results.extend(g)

        if not all_results:
            return {"score": 0.0, "count": 0, "source": "macro_news"}

        weighted_scores, weights = [], []
        for text, source in all_results:
            s = finbert_score(text)
            w = _source_weight(source)
            weighted_scores.append(s * w)
            weights.append(w)

        total_w = sum(weights)
        score = sum(weighted_scores) / total_w if total_w > 0 else 0.0
        return {"score": float(score), "count": len(all_results), "source": "macro_news"}


# ─── Google Trends ────────────────────────────────────────────────────────────


class GoogleTrendsSentiment:
    KEYWORDS = ["ethereum", "eth price", "buy ethereum"]

    def get_score(self) -> Dict[str, Any]:
        try:
            pytrends = TrendReq(hl="en-US", tz=0)
            pytrends.build_payload(self.KEYWORDS, cat=0, timeframe="now 7-d", geo="")
            data = pytrends.interest_over_time()
            if data.empty:
                return {"score": 0.0, "source": "google_trends"}
            # Normalise: 0=cold (score -1), 100=hot (score +1)
            avg = float(data[self.KEYWORDS].mean().mean())
            score = (avg - 50) / 50
            return {"score": score, "source": "google_trends", "avg_interest": avg}
        except Exception as exc:
            logger.warning("google_trends_error", error=str(exc))
            return {"score": 0.0, "source": "google_trends"}


# ─── Aggregator ───────────────────────────────────────────────────────────────


class SentimentAggregator:
    """
    Combines all sentiment sources into a single composite score.
    Weights reflect signal quality:
      news        30%
      twitter     25%
      reddit      15%
      macro_news  20%
      trends      10%
    """

    WEIGHTS = {
        "news": 0.30,
        "twitter": 0.25,
        "reddit": 0.15,
        "macro_news": 0.20,
        "google_trends": 0.10,
    }

    def __init__(self) -> None:
        self._twitter = TwitterSentiment()
        self._reddit = RedditSentiment()
        self._news = NewsSentiment()
        self._macro = MacroNewsSentiment()
        self._trends = GoogleTrendsSentiment()

    async def get_composite_score(self) -> Dict[str, Any]:
        twitter_task = self._twitter.get_score()
        news_task = self._news.get_score()
        macro_task = self._macro.get_score()

        twitter_res, news_res, macro_res = await asyncio.gather(
            twitter_task, news_task, macro_task
        )

        reddit_res = await asyncio.get_event_loop().run_in_executor(
            None, self._reddit.get_score
        )
        trends_res = await asyncio.get_event_loop().run_in_executor(
            None, self._trends.get_score
        )

        components = {
            "twitter": twitter_res,
            "news": news_res,
            "macro_news": macro_res,
            "reddit": reddit_res,
            "google_trends": trends_res,
        }

        composite = sum(
            components[k]["score"] * self.WEIGHTS[k]
            for k in self.WEIGHTS
            if components[k]["score"] is not None
        )
        composite = float(np.clip(composite, -1.0, 1.0))

        result = {
            "composite": composite,
            "components": {k: v["score"] for k, v in components.items()},
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "bullish": composite > 0.2,
            "bearish": composite < -0.2,
        }
        logger.info(
            "sentiment_computed",
            composite=composite,
            twitter=twitter_res["score"],
            news=news_res["score"],
        )
        return result

    async def close(self) -> None:
        await self._twitter.close()
