from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging
import re

from ..models.conversation import Conversation, Message, MessageSender, SentimentLabel
from ..core.time import utcnow_naive
from ..config import settings
from .sentiment_llm import analyze_sentiment_with_llm
from .sentiment_enhanced import analyze_sentiment_enhanced

logger = logging.getLogger(__name__)


def _label_from_neg_one_to_one(score: float) -> str:
    """Map -1..1 score to positive | neutral | negative (same thresholds as lexicon)."""
    if score > 0.2:
        return "positive"
    if score < -0.2:
        return "negative"
    return "neutral"


class SentimentService:
    """
    Sentiment analysis service for HR assistant.
    
    Supports:
    - Text sentiment analysis (positive, neutral, negative)
    - Batch analysis
    - Trend analysis over time
    - Alert triggering for negative patterns
    
    In production, this would integrate with Azure AI Text Analytics.
    """
    
    # Lexicon-based fallback sentiment rules.
    POSITIVE_WORDS = {
        "good", "great", "excellent", "love", "amazing", "happy",
        "thanks", "thank", "awesome", "fantastic", "wonderful",
        "helpful", "appreciate", "pleasant", "satisfied",
        "best", "perfect", "glad", "pleased", "excited", "resolved",
        "quick", "supportive", "calm", "clear",
    }
    NEGATIVE_WORDS = {
        "bad", "terrible", "hate", "awful", "poor", "worst",
        "angry", "frustrated", "disappointed", "upset", "annoyed",
        "horrible", "useless", "waste", "difficult", "confusing",
        "slow", "rude", "unhappy", "stressed", "overwhelmed",
        "burnout", "anxious", "ignored", "harassed", "unsafe",
    }
    NEGATIVE_PHRASES = {
        "not happy",
        "not helpful",
        "not good",
        "not satisfied",
        "no support",
        "too much workload",
        "manager ignores",
    }
    POSITIVE_PHRASES = {
        "very helpful",
        "really helpful",
        "feel better",
        "much better",
        "thank you",
    }
    NEGATORS = {"not", "never", "no", "hardly", "barely", "without"}
    AMPLIFIERS = {"very", "really", "extremely", "super", "too", "so"}
    DOWNTONERS = {"slightly", "somewhat", "little", "bit"}
    EMOTION_HINTS = {
        "stress": ("stressed", "overwhelmed", "burnout", "exhausted", "drained"),
        "frustration": ("frustrated", "annoyed", "ignored", "blocked", "stuck"),
        "anxiety": ("anxious", "worried", "nervous", "panic"),
        "sadness": ("sad", "hopeless", "down", "disappointed"),
        "anger": ("angry", "furious", "rage", "mad"),
        "gratitude": ("thank", "thanks", "appreciate", "grateful"),
        "satisfaction": ("happy", "pleased", "great", "excellent", "resolved"),
    }
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
    
    def _analyze_lexicon(self, text: str) -> Dict:
        """Deterministic lexicon + negation rules (-1..1 score)."""
        text_lower = text.lower().strip()
        tokens = re.findall(r"[a-z']+", text_lower)
        score = 0.0

        for phrase in self.POSITIVE_PHRASES:
            if phrase in text_lower:
                score += 0.35
        for phrase in self.NEGATIVE_PHRASES:
            if phrase in text_lower:
                score -= 0.45

        for index, token in enumerate(tokens):
            if token not in self.POSITIVE_WORDS and token not in self.NEGATIVE_WORDS:
                continue

            window = tokens[max(0, index - 2):index]
            negated = any(w in self.NEGATORS for w in window)
            amplified = any(w in self.AMPLIFIERS for w in window)
            down_toned = any(w in self.DOWNTONERS for w in window)

            magnitude = 0.28
            if amplified:
                magnitude += 0.14
            if down_toned:
                magnitude -= 0.10
            magnitude = max(0.12, magnitude)

            polarity = 1.0 if token in self.POSITIVE_WORDS else -1.0
            if negated:
                polarity *= -1.0
            score += polarity * magnitude

        exclamations = text.count("!")
        if exclamations > 0:
            score *= min(1.0 + (0.06 * exclamations), 1.2)
        score = max(-1.0, min(1.0, score))
        label = _label_from_neg_one_to_one(score)

        return {
            "sentiment": label,
            "score": round(score, 3),
            "text": text,
            "source": "lexicon",
        }

    def analyze(self, text: str, conversation_id: Optional[UUID] = None) -> Dict:
        """
        Analyze sentiment of a single text.

        When USE_ENHANCED_SENTIMENT is enabled, uses context-aware analyzer with
        sarcasm detection, emoji support, and improved emotion detection.
        
        When SENTIMENT_HYBRID_ENABLED and Azure is configured, tries LLM JSON classification
        first; always falls back to lexicon on failure or when hybrid is off.

        Returns:
            Dict with sentiment label, score (-1 to 1), text, and source (lexicon|llm|hybrid|enhanced).
        """
        if not text or not text.strip():
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "text": text,
                "source": "lexicon",
            }

        # Use enhanced sentiment analyzer when configured
        if settings.USE_ENHANCED_SENTIMENT:
            enhanced_result = analyze_sentiment_enhanced(text, conversation_id)
            # Convert enhanced score (-1 to 1) and format to match existing interface
            return {
                "sentiment": enhanced_result["sentiment"],
                "score": enhanced_result["score"],
                "text": text,
                "source": "enhanced",
                "confidence": enhanced_result.get("confidence"),
                "intensity": enhanced_result.get("intensity"),
                "emotions": enhanced_result.get("emotions"),
                "sarcasm": enhanced_result.get("sarcasm"),
            }

        if settings.SENTIMENT_HYBRID_ENABLED:
            llm_result = analyze_sentiment_with_llm(text)
            if llm_result:
                lex = self._analyze_lexicon(text)
                llm_score = float(llm_result["score"])
                llm_label = str(llm_result["sentiment"])
                lex_score = float(lex["score"])
                gap = abs(llm_score - lex_score)
                gap_thr = max(0.05, float(settings.SENTIMENT_BLEND_SCORE_GAP_THRESHOLD))
                disagree = (llm_label != lex["sentiment"]) or (gap >= gap_thr)

                if settings.SENTIMENT_BLEND_ON_DISAGREEMENT and disagree:
                    w = max(0.0, min(1.0, float(settings.SENTIMENT_BLEND_LLM_WEIGHT)))
                    blended = w * llm_score + (1.0 - w) * lex_score
                    blended = max(-1.0, min(1.0, round(blended, 3)))
                    label = _label_from_neg_one_to_one(blended)
                    out = {
                        "sentiment": label,
                        "score": blended,
                        "text": text,
                        "source": "hybrid",
                    }
                    logger.info(
                        "Sentiment analysis (hybrid llm+lexicon): %s (%s) disagree=%s gap=%.2f",
                        out["sentiment"],
                        out["score"],
                        llm_label != lex["sentiment"],
                        gap,
                    )
                    return out

                out = {
                    "sentiment": llm_label,
                    "score": llm_score,
                    "text": text,
                    "source": "llm",
                }
                logger.info(
                    "Sentiment analysis (llm): %s (%s)",
                    out["sentiment"],
                    out["score"],
                )
                return out

        lex = self._analyze_lexicon(text)
        logger.info(
            "Sentiment analysis (lexicon): %s (%s)",
            lex["sentiment"],
            lex["score"],
        )
        return lex

    def analyze_lexicon_only(self, text: str) -> Dict:
        """Fast path for chat hot paths: same shape as analyze(), no LLM."""
        if not text or not text.strip():
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "text": text,
                "source": "lexicon",
            }
        return self._analyze_lexicon(text)
    
    def analyze_batch(self, texts: List[str]) -> List[Dict]:
        """
        Analyze sentiment for multiple texts.
        
        Args:
            texts: List of text strings to analyze
            
        Returns:
            List of sentiment analysis results
        """
        return [self.analyze(text) for text in texts]

    def detect_emotion(self, text: str, *, sentiment: Optional[str] = None) -> Dict:
        """
        Lightweight emotion tagging for one user utterance.
        Returns primary emotion + optional secondary cues.
        """
        normalized = (text or "").strip().lower()
        if not normalized:
            return {
                "emotion": "neutral",
                "secondary_emotions": [],
                "confidence": 0.0,
                "sentiment": "neutral",
                "score": 0.0,
            }

        sentiment_result = self.analyze(text)
        effective_sentiment = sentiment or str(sentiment_result.get("sentiment", "neutral"))
        score = float(sentiment_result.get("score", 0.0))

        hits: list[tuple[str, int]] = []
        for emotion, keywords in self.EMOTION_HINTS.items():
            count = sum(1 for keyword in keywords if keyword in normalized)
            if count > 0:
                hits.append((emotion, count))

        if not hits:
            fallback = "neutral"
            if effective_sentiment == "negative":
                fallback = "frustration"
            elif effective_sentiment == "positive":
                fallback = "satisfaction"
            return {
                "emotion": fallback,
                "secondary_emotions": [],
                "confidence": 0.55 if fallback != "neutral" else 0.4,
                "sentiment": effective_sentiment,
                "score": score,
            }

        hits.sort(key=lambda item: item[1], reverse=True)
        primary = hits[0][0]
        secondary = [name for name, _ in hits[1:3]]
        max_hits = max(1, hits[0][1])
        confidence = min(0.95, 0.55 + (0.12 * max_hits))
        return {
            "emotion": primary,
            "secondary_emotions": secondary,
            "confidence": round(confidence, 2),
            "sentiment": effective_sentiment,
            "score": score,
        }
    
    def get_trend(self, user_id: Optional[UUID] = None, days: int = 7) -> Dict:
        """
        Get sentiment trend analysis.
        
        In production, this would query the sentiment history from the database
        and calculate actual trends based on stored data.
        
        Args:
            user_id: Optional user ID to filter trends
            days: Number of days to analyze (default: 7)
            
        Returns:
            Dict with trend statistics
        """
        days = max(1, min(days, 90))
        end_date = utcnow_naive()
        start_date = end_date - timedelta(days=days)

        if not self.db:
            return {
                "average_sentiment": 0.0,
                "trend": "stable",
                "positive_percentage": 0.0,
                "negative_percentage": 0.0,
                "neutral_percentage": 100.0,
                "total_analyses": 0,
                "period_days": days,
            }

        query = (
            self.db.query(Message.sentiment, func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Message.sender == MessageSender.user,
                Message.created_at >= start_date,
                Message.sentiment.isnot(None),
            )
        )

        if user_id:
            query = query.filter(Conversation.user_id == user_id)

        rows = query.group_by(Message.sentiment).all()

        counts = {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
        }
        for sentiment, count in rows:
            if sentiment == SentimentLabel.positive:
                counts["positive"] += int(count)
            elif sentiment == SentimentLabel.negative:
                counts["negative"] += int(count)
            else:
                counts["neutral"] += int(count)

        total = counts["positive"] + counts["neutral"] + counts["negative"]
        if total == 0:
            return {
                "average_sentiment": 0.0,
                "trend": "stable",
                "positive_percentage": 0.0,
                "negative_percentage": 0.0,
                "neutral_percentage": 100.0,
                "total_analyses": 0,
                "period_days": days,
            }

        positive_pct = (counts["positive"] / total) * 100.0
        negative_pct = (counts["negative"] / total) * 100.0
        neutral_pct = (counts["neutral"] / total) * 100.0

        sentiment_score = (
            (counts["positive"] * 1.0)
            + (counts["neutral"] * 0.0)
            + (counts["negative"] * -1.0)
        ) / total

        if sentiment_score > 0.2:
            trend_label = "improving"
        elif sentiment_score < -0.2:
            trend_label = "declining"
        else:
            trend_label = "stable"

        return {
            "average_sentiment": round(sentiment_score, 3),
            "trend": trend_label,
            "positive_percentage": round(positive_pct, 1),
            "negative_percentage": round(negative_pct, 1),
            "neutral_percentage": round(neutral_pct, 1),
            "total_analyses": total,
            "period_days": days,
        }
    
    def should_trigger_alert(self, sentiment: str, score: float) -> bool:
        """
        Determine if negative sentiment should trigger an alert.
        
        Args:
            sentiment: Sentiment label (positive, neutral, negative)
            score: Sentiment score (-1 to 1)
            
        Returns:
            True if alert should be triggered
        """
        # Trigger alert for strongly negative sentiment
        if sentiment == "negative" and score < -0.5:
            return True
        return False
    
    def check_negative_patterns(self, recent_sentiments: List[Dict]) -> Optional[Dict]:
        """
        Check for patterns of negative sentiment that may need attention.
        
        Args:
            recent_sentiments: List of recent sentiment analysis results
            
        Returns:
            Dict with alert info if pattern detected, None otherwise
        """
        if len(recent_sentiments) < 3:
            return None
        
        negative_count = sum(1 for s in recent_sentiments if s.get("sentiment") == "negative")
        negative_ratio = negative_count / len(recent_sentiments)
        
        # Alert if more than 50% are negative in recent analyses
        if negative_ratio > 0.5:
            return {
                "alert": True,
                "message": "Pattern of negative sentiment detected",
                "negative_count": negative_count,
                "total_count": len(recent_sentiments),
                "negative_percentage": round(negative_ratio * 100, 1)
            }
        
        return None

    def log_sentiment(
        self,
        user_id: UUID,
        text: str,
        sentiment: Optional[str] = None,
    ) -> None:
        """
        Persist a sentiment observation for analytics dashboards.

        Strategy: try to write to a `sentiment_logs` table if the model
        exists, otherwise silently no-op so we never break the chat flow.
        sentiment can be 'positive', 'neutral', or 'negative'.
        """
        if not self.db:
            return

        # Resolve sentiment if not pre-computed
        if sentiment is None:
            result = self.analyze(text)
            sentiment = result.get("sentiment", "neutral")

        try:
            # Import lazily to avoid circular imports
            from ..models.sentiment_log import SentimentLog  # type: ignore[import]

            label_map = {
                "positive": SentimentLabel.positive,
                "neutral": SentimentLabel.neutral,
                "negative": SentimentLabel.negative,
            }
            log_entry = SentimentLog(
                user_id=user_id,
                score=1.0 if sentiment == "positive" else (-1.0 if sentiment == "negative" else 0.0),
                sentiment=label_map.get(sentiment, SentimentLabel.neutral),
            )
            self.db.add(log_entry)
            self.db.commit()
        except ImportError:
            # Model not yet created — log to application log only
            logger.info(f"sentiment_log model unavailable; skipped DB write for user {user_id}: {sentiment}")
        except Exception as exc:
            self.db.rollback()
            logger.warning(f"Failed to persist sentiment log: {exc}")

    def analyze_and_log(self, user_id: UUID, text: str) -> Dict:
        """Analyze text sentiment and persist the result. Returns the analysis dict."""
        result = self.analyze(text)
        self.log_sentiment(user_id=user_id, text=text, sentiment=result.get("sentiment"))
        return result
