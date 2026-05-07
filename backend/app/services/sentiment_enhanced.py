"""Enhanced sentiment analysis with context awareness, sarcasm detection, and improved emotion detection."""

from typing import Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta, timezone
import re
import logging

logger = logging.getLogger(__name__)

# Enhanced lexicon with HR-specific terms and intensity weighting
SENTIMENT_LEXICON = {
    # Strong positive (weight: 0.8)
    "excellent": 0.8, "amazing": 0.8, "outstanding": 0.8, "fantastic": 0.8,
    "wonderful": 0.8, "brilliant": 0.8, "perfect": 0.8, "love": 0.8,
    "thrilled": 0.8, "ecstatic": 0.8, "delighted": 0.8, "grateful": 0.8,
    
    # Moderate positive (weight: 0.5)
    "good": 0.5, "great": 0.5, "happy": 0.5, "pleased": 0.5, "satisfied": 0.5,
    "helpful": 0.5, "supportive": 0.5, "appreciate": 0.5, "thanks": 0.5,
    "thank": 0.5, "glad": 0.5, "excited": 0.5, "resolved": 0.5, "clear": 0.5,
    "smooth": 0.5, "easy": 0.5, "comfortable": 0.5, "confident": 0.5,
    
    # Weak positive (weight: 0.3)
    "nice": 0.3, "okay": 0.3, "fine": 0.3, "alright": 0.3, "decent": 0.3,
    "fair": 0.3, "reasonable": 0.3, "acceptable": 0.3, "better": 0.3,
    
    # Strong negative (weight: -0.8)
    "terrible": -0.8, "horrible": -0.8, "awful": -0.8, "hate": -0.8,
    "disgusting": -0.8, "appalling": -0.8, "atrocious": -0.8, "dreadful": -0.8,
    "furious": -0.8, "outraged": -0.8, "devastated": -0.8, "miserable": -0.8,
    "toxic": -0.8, "abusive": -0.8, "harassed": -0.8, "discriminated": -0.8,
    
    # Moderate negative (weight: -0.5)
    "bad": -0.5, "poor": -0.5, "disappointed": -0.5, "frustrated": -0.5,
    "annoyed": -0.5, "upset": -0.5, "angry": -0.5, "stressed": -0.5,
    "worried": -0.5, "concerned": -0.5, "unhappy": -0.5, "unsatisfied": -0.5,
    "difficult": -0.5, "confusing": -0.5, "complicated": -0.5, "slow": -0.5,
    "unfair": -0.5, "unreasonable": -0.5, "unclear": -0.5, "problem": -0.5,
    "issue": -0.5, "trouble": -0.5, "struggle": -0.5, "burnout": -0.5,
    "burned": -0.5, "burnt": -0.5, "overwhelmed": -0.5, "exhausted": -0.5,
    "drained": -0.5, "tired": -0.5, "weary": -0.5, "fatigued": -0.5,
    
    # Weak negative (weight: -0.3)
    "boring": -0.3, "dull": -0.3, "mediocre": -0.3, "lacking": -0.3,
    "insufficient": -0.3, "inadequate": -0.3, "lacking": -0.3, "weak": -0.3,
}

# HR-specific compound phrases
HR_PHRASES = {
    # Positive HR phrases
    "work-life balance": 0.6,
    "great benefits": 0.7,
    "competitive salary": 0.6,
    "good culture": 0.7,
    "supportive manager": 0.8,
    "career growth": 0.6,
    "professional development": 0.5,
    "flexible hours": 0.5,
    "remote work": 0.4,
    "team collaboration": 0.5,
    "inclusive environment": 0.7,
    "psychological safety": 0.6,
    "wellness program": 0.5,
    "mental health support": 0.6,
    "fair compensation": 0.5,
    "transparent communication": 0.5,
    "employee recognition": 0.6,
    "learning opportunities": 0.5,
    "meaningful work": 0.6,
    "purpose-driven": 0.5,
    
    # Negative HR phrases
    "micromanagement": -0.8,
    "toxic culture": -0.9,
    "hostile environment": -0.9,
    "bullying": -0.9,
    "discrimination": -0.9,
    "harassment": -0.9,
    "unpaid overtime": -0.7,
    "unreasonable deadline": -0.7,
    "lack of resources": -0.6,
    "poor management": -0.8,
    "bad leadership": -0.8,
    "high turnover": -0.6,
    "job insecurity": -0.7,
    "favoritism": -0.7,
    "glass ceiling": -0.6,
    "wage gap": -0.7,
    "overworked": -0.7,
    "underpaid": -0.7,
    "no work-life balance": -0.8,
    "burnout culture": -0.8,
    "stressful environment": -0.7,
    "lack of support": -0.6,
    "no recognition": -0.6,
    "unfair treatment": -0.8,
    "zero tolerance": -0.5,
    "disciplinary action": -0.5,
    "performance improvement plan": -0.4,
    "pip": -0.4,
    "laid off": -0.8,
    "fired": -0.9,
    "terminated": -0.9,
    "redundancy": -0.7,
    "restructuring": -0.5,
}

# Emoji sentiment mapping
EMOJI_SENTIMENT = {
    # Positive emojis
    "😊": 0.7, "😄": 0.8, "😃": 0.8, "😁": 0.7, "😆": 0.6,
    "🙂": 0.5, "🙃": 0.3, "😉": 0.4, "😌": 0.5, "😍": 0.9,
    "🥰": 0.9, "😘": 0.7, "😗": 0.6, "😙": 0.6, "😚": 0.6,
    "🥳": 0.8, "🎉": 0.7, "👍": 0.6, "🙌": 0.7, "💪": 0.5,
    "❤️": 0.8, "💖": 0.8, "💯": 0.7, "✨": 0.6, "🌟": 0.7,
    "🎊": 0.7, "🌈": 0.5, "☀️": 0.5, "🔥": 0.6, "👏": 0.7,
    "🙏": 0.5, "💐": 0.6, "🌺": 0.5, "🌸": 0.5, "🎁": 0.6,
    "🎈": 0.5, "🏆": 0.7, "🥇": 0.7, "🎯": 0.5, "✅": 0.5,
    
    # Negative emojis
    "😞": -0.6, "😔": -0.6, "😟": -0.5, "😕": -0.4, "🙁": -0.5,
    "☹️": -0.6, "😣": -0.7, "😖": -0.7, "😫": -0.7, "😩": -0.8,
    "🥺": -0.5, "😢": -0.7, "😭": -0.8, "😤": -0.7, "😠": -0.7,
    "😡": -0.8, "🤬": -0.9, "🤯": -0.6, "😳": -0.4, "🥵": -0.5,
    "🥶": -0.4, "😱": -0.7, "😨": -0.6, "😰": -0.6, "😥": -0.6,
    "😓": -0.5, "🤗": -0.3, "🤔": -0.2, "🤭": -0.2, "🤫": -0.2,
    "🤥": -0.5, "😶": -0.3, "😐": -0.2, "😑": -0.3, "😬": -0.4,
    "🙄": -0.5, "😯": -0.3, "😦": -0.4, "😧": -0.5, "😮": -0.3,
    "😲": -0.4, "🥱": -0.4, "😴": -0.3, "🤤": -0.3, "😪": -0.4,
    "😵": -0.6, "🤐": -0.4, "🥴": -0.5, "🤢": -0.6, "🤮": -0.7,
    "🤧": -0.4, "😷": -0.4, "🤒": -0.4, "🤕": -0.5, "💀": -0.5,
    "☠️": -0.6, "👎": -0.6, "💔": -0.7, "😈": -0.5, "👿": -0.6,
    "💩": -0.5, "🤡": -0.5, "❌": -0.5, "🚫": -0.5, "⛔": -0.5,
}

# Sarcasm patterns
SARCASM_PATTERNS = [
    r"oh\s+(great|wonderful|perfect|fantastic|lovely|brilliant)",
    r"just\s+(what\s+i\s+needed|what\s+i\s+wanted|perfect)",
    r"yeah\s+(right|sure|okay|ok)",
    r"sure\s+(thing|whatever)",
    r"(great|wonderful|perfect|lovely)\s+timing",
    r"(exactly|precisely)\s+what\s+i\s+(needed|wanted)",
    r"couldn't\s+be\s+(better|happier)",
    r"just\s+peachy",
    r"(love|adore)\s+it\s+when",
    r"my\s+favorite\s+(thing|part)",
    r"(fantastic|wonderful|great)\s+news",
    r"(perfect|ideal)\s+solution",
    r"(?:^|\s)(?:oh|ah|wow)\s+(?:great|wonderful|fantastic|perfect|lovely|brilliant|awesome)",
]

SARCASM_PATTERNS_COMPILED = [re.compile(pattern, re.IGNORECASE) for pattern in SARCASM_PATTERNS]

# Negation words and their scope
NEGATION_WORDS = {"not", "no", "never", "neither", "nor", "none", "nothing", "nobody",
                  "nowhere", "hardly", "scarcely", "barely", "without", "lack", "missing",
                  "except", "but", "apart", "away", "down", "off", "out"}

INTENSIFIERS = {"very", "really", "extremely", "incredibly", "absolutely", "completely",
                "totally", "utterly", "quite", "rather", "pretty", "fairly", "really",
                "so", "too", "highly", "deeply", "strongly", "definitely", "certainly",
                "surely", "undoubtedly", "clearly", "obviously", "particularly", "especially"}

DIMINISHERS = {"slightly", "somewhat", "a bit", "a little", "kind of", "sort of",
               "barely", "hardly", "scarcely", "moderately", "relatively", "fairly",
               "reasonably", "tolerably", "passably", "marginally"}

# Context window for conversation-aware sentiment
CONTEXT_WINDOW_SIZE = 5


class ContextAwareSentimentAnalyzer:
    """Advanced sentiment analyzer with context awareness and sarcasm detection."""
    
    def __init__(self):
        self.conversation_history: Dict[UUID, List[Dict]] = {}
    
    def _extract_emojis(self, text: str) -> List[Tuple[str, float]]:
        """Extract emojis and their sentiment scores from text."""
        emojis = []
        for emoji_char, score in EMOJI_SENTIMENT.items():
            if emoji_char in text:
                count = text.count(emoji_char)
                emojis.append((emoji_char, score * count))
        return emojis
    
    def _detect_sarcasm(self, text: str) -> Tuple[bool, float]:
        """Detect sarcasm in text. Returns (is_sarcastic, confidence)."""
        text_lower = text.lower()
        
        # Check sarcasm patterns
        sarcasm_hits = 0
        for pattern in SARCASM_PATTERNS_COMPILED:
            if pattern.search(text_lower):
                sarcasm_hits += 1
        
        # Check for positive words in negative context
        positive_count = sum(1 for word in SENTIMENT_LEXICON if SENTIMENT_LEXICON[word] > 0 and word in text_lower)
        negative_context = any(word in text_lower for word in ["but", "however", "although", "though", "except"])
        
        if positive_count > 0 and negative_context:
            sarcasm_hits += 1
        
        # Check for excessive punctuation (multiple !!! or ???)
        if re.search(r'!{2,}|\?{2,}', text):
            sarcasm_hits += 0.5
        
        is_sarcastic = sarcasm_hits >= 1
        confidence = min(0.95, 0.5 + (0.15 * sarcasm_hits))
        
        return is_sarcastic, confidence
    
    def _analyze_lexicon_enhanced(self, text: str) -> Tuple[float, Dict]:
        """
        Enhanced lexicon-based analysis with phrase detection, negation handling,
        intensity modifiers, and emoji support.
        
        Returns: (score, metadata)
        """
        text_lower = text.lower().strip()
        if not text_lower:
            return 0.0, {"method": "empty"}
        
        score = 0.0
        metadata = {
            "method": "enhanced_lexicon",
            "words_found": [],
            "phrases_found": [],
            "emojis_found": [],
            "negations": 0,
            "intensifiers": 0,
            "diminishers": 0,
        }
        
        # 1. Check for HR-specific phrases first (higher priority)
        for phrase, weight in HR_PHRASES.items():
            if phrase in text_lower:
                score += weight
                metadata["phrases_found"].append((phrase, weight))
        
        # 2. Token-based analysis with context window
        tokens = re.findall(r'\b\w+\b', text_lower)
        
        for i, token in enumerate(tokens):
            if token in SENTIMENT_LEXICON:
                word_score = SENTIMENT_LEXICON[token]
                
                # Check negation in context window (3 tokens before)
                context_start = max(0, i - 3)
                context_window = tokens[context_start:i]
                
                negated = any(neg in context_window for neg in NEGATION_WORDS)
                intensified = any(intens in context_window for intens in INTENSIFIERS)
                diminished = any(dim in context_window for dim in DIMINISHERS)
                
                if negated:
                    word_score *= -1.0
                    metadata["negations"] += 1
                
                if intensified:
                    word_score *= 1.4
                    metadata["intensifiers"] += 1
                
                if diminished:
                    word_score *= 0.6
                    metadata["diminishers"] += 1
                
                score += word_score
                metadata["words_found"].append((token, word_score))
        
        # 3. Emoji analysis
        emojis = self._extract_emojis(text)
        for emoji_char, emoji_score in emojis:
            score += emoji_score
            metadata["emojis_found"].append((emoji_char, emoji_score))
        
        # 4. Punctuation intensity
        exclamation_count = text.count('!')
        question_count = text.count('?')
        
        if exclamation_count > 0:
            # Exclamations amplify sentiment
            amplification = min(0.2, 0.05 * exclamation_count)
            score = score * (1 + amplification) if score > 0 else score * (1 - amplification)
        
        if question_count > 1:
            # Multiple questions suggest confusion/frustration
            score -= 0.1 * min(question_count - 1, 3)
        
        # 5. All-caps words (shouting)
        caps_words = re.findall(r'\b[A-Z]{2,}\b', text)
        if caps_words:
            score = score * 1.2 if score > 0 else score * 1.2
        
        # Clamp score
        score = max(-1.0, min(1.0, score))
        
        return score, metadata
    
    def _get_conversation_context(self, conversation_id: UUID) -> List[Dict]:
        """Get recent messages from conversation history."""
        return self.conversation_history.get(conversation_id, [])[-CONTEXT_WINDOW_SIZE:]
    
    def _compute_context_adjustment(self, current_score: float, 
                                   conversation_id: Optional[UUID]) -> float:
        """
        Adjust current sentiment based on conversation context.
        If sentiment is shifting dramatically, it might indicate escalation or recovery.
        """
        if not conversation_id:
            return current_score
        
        history = self._get_conversation_context(conversation_id)
        if len(history) < 2:
            return current_score
        
        # Calculate trend
        recent_scores = [msg["score"] for msg in history if "score" in msg]
        if not recent_scores:
            return current_score
        
        avg_recent = sum(recent_scores) / len(recent_scores)
        
        # Detect dramatic shifts
        shift = current_score - avg_recent
        
        # If shift is dramatic (>0.5), it might need attention
        if abs(shift) > 0.5:
            # Weight towards the new sentiment but keep some history
            adjusted = (current_score * 0.7) + (avg_recent * 0.3)
            return adjusted
        
        # Normal case: slight smoothing
        adjusted = (current_score * 0.8) + (avg_recent * 0.2)
        return adjusted
    
    def analyze(self, text: str, conversation_id: Optional[UUID] = None,
                user_id: Optional[UUID] = None) -> Dict:
        """
        Analyze sentiment with full enhancements.
        
        Args:
            text: Text to analyze
            conversation_id: Optional conversation ID for context awareness
            user_id: Optional user ID for tracking
            
        Returns:
            Dict with sentiment, score, confidence, emotions, sarcasm detection, etc.
        """
        if not text or not text.strip():
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "intensity": "low",
                "sarcasm": {"detected": False, "confidence": 0.0},
                "emotions": {"primary": "neutral", "secondary": []},
                "context_adjusted": False,
                "text": text,
            }
        
        # 1. Enhanced lexicon analysis
        score, metadata = self._analyze_lexicon_enhanced(text)
        
        # 2. Sarcasm detection
        is_sarcastic, sarcasm_confidence = self._detect_sarcasm(text)
        
        # If sarcasm detected with high confidence, invert the sentiment
        if is_sarcastic and sarcasm_confidence > 0.7:
            score = -score * 0.8  # Partial inversion
            metadata["sarcasm_adjusted"] = True
        
        # 3. Context adjustment
        original_score = score
        score = self._compute_context_adjustment(score, conversation_id)
        context_adjusted = abs(score - original_score) > 0.05
        
        # 4. Determine label
        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"
        
        # 5. Calculate confidence based on evidence
        evidence_count = (len(metadata.get("words_found", [])) + 
                         len(metadata.get("phrases_found", [])) +
                         len(metadata.get("emojis_found", [])))
        confidence = min(0.95, 0.4 + (0.1 * evidence_count))
        
        # 6. Calculate intensity
        abs_score = abs(score)
        if abs_score > 0.7:
            intensity = "high"
        elif abs_score > 0.4:
            intensity = "medium"
        else:
            intensity = "low"
        
        # 7. Emotion detection
        emotions = self._detect_emotions(text, label)
        
        # 8. Update conversation history
        if conversation_id:
            if conversation_id not in self.conversation_history:
                self.conversation_history[conversation_id] = []
            self.conversation_history[conversation_id].append({
                "text": text,
                "score": score,
                "label": label,
                "timestamp": datetime.now(timezone.utc),
            })
            # Keep only recent messages
            self.conversation_history[conversation_id] = \
                self.conversation_history[conversation_id][-CONTEXT_WINDOW_SIZE:]
        
        return {
            "sentiment": label,
            "score": round(score, 3),
            "original_score": round(original_score, 3),
            "confidence": round(confidence, 2),
            "intensity": intensity,
            "sarcasm": {
                "detected": is_sarcastic,
                "confidence": round(sarcasm_confidence, 2),
                "adjusted": metadata.get("sarcasm_adjusted", False),
            },
            "emotions": emotions,
            "context_adjusted": context_adjusted,
            "metadata": metadata,
            "text": text[:200],  # Truncated for privacy
        }
    
    def _detect_emotions(self, text: str, sentiment: str) -> Dict:
        """
        Detect specific emotions from text with confidence scores.
        """
        text_lower = text.lower()
        
        emotion_keywords = {
            "joy": ["happy", "joyful", "excited", "thrilled", "delighted", "cheerful", "elated", "euphoric"],
            "gratitude": ["grateful", "thankful", "appreciative", "blessed", "indebted"],
            "satisfaction": ["satisfied", "content", "pleased", "fulfilled", "comfortable"],
            "relief": ["relieved", "relief", "relaxed", "calm", "peaceful", "serene"],
            "pride": ["proud", "accomplished", "achieved", "successful", "confident"],
            "optimism": ["hopeful", "optimistic", "positive", "encouraged", "inspired"],
            "frustration": ["frustrated", "annoyed", "irritated", "aggravated", "exasperated"],
            "anger": ["angry", "furious", "rage", "livid", "irate", "enraged"],
            "anxiety": ["anxious", "worried", "nervous", "stressed", "tense", "uneasy", "apprehensive"],
            "sadness": ["sad", "depressed", "melancholy", "gloomy", "sorrowful", "dejected"],
            "disappointment": ["disappointed", "let down", "disillusioned", "discouraged"],
            "confusion": ["confused", "puzzled", "perplexed", "bewildered", "uncertain", "lost"],
            "fear": ["afraid", "scared", "terrified", "frightened", "fearful", "panicked"],
            "loneliness": ["lonely", "isolated", "alone", "abandoned", "neglected", "disconnected"],
            "exhaustion": ["exhausted", "tired", "drained", "weary", "burned out", "fatigued"],
            "overwhelm": ["overwhelmed", "overloaded", "swamped", "buried", "drowning"],
            "betrayal": ["betrayed", "cheated", "deceived", "lied", "backstabbed"],
            "injustice": ["unfair", "unjust", "biased", "prejudiced", "discriminated"],
        }
        
        emotion_scores = {}
        for emotion, keywords in emotion_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            if score > 0:
                emotion_scores[emotion] = score
        
        if not emotion_scores:
            return {
                "primary": "neutral" if sentiment == "neutral" else ("satisfaction" if sentiment == "positive" else "frustration"),
                "secondary": [],
                "all_emotions": [],
            }
        
        # Sort by score
        sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_emotions[0][0]
        secondary = [e[0] for e in sorted_emotions[1:3] if e[1] >= sorted_emotions[0][1] * 0.5]
        
        return {
            "primary": primary,
            "secondary": secondary,
            "all_emotions": [{"emotion": e[0], "score": e[1]} for e in sorted_emotions[:5]],
        }
    
    def get_conversation_sentiment_summary(self, conversation_id: UUID) -> Dict:
        """Get aggregated sentiment summary for a conversation."""
        history = self.conversation_history.get(conversation_id, [])
        
        if not history:
            return {
                "message_count": 0,
                "average_score": 0.0,
                "trend": "stable",
                "dominant_sentiment": "neutral",
                "emotional_journey": [],
            }
        
        scores = [msg["score"] for msg in history]
        labels = [msg["label"] for msg in history]
        
        avg_score = sum(scores) / len(scores)
        
        # Determine trend
        if len(scores) >= 3:
            first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
            second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            
            if second_half > first_half + 0.2:
                trend = "improving"
            elif second_half < first_half - 0.2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        # Dominant sentiment
        label_counts: Dict[str, int] = {}
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1
        dominant = max(label_counts.items(), key=lambda x: x[1])[0]
        
        return {
            "message_count": len(history),
            "average_score": round(avg_score, 3),
            "trend": trend,
            "dominant_sentiment": dominant,
            "emotional_journey": [{"score": msg["score"], "label": msg["label"]} for msg in history],
        }
    
    def clear_conversation_history(self, conversation_id: UUID) -> None:
        """Clear conversation history."""
        if conversation_id in self.conversation_history:
            del self.conversation_history[conversation_id]


# Global instance for easy access
_enhanced_analyzer = ContextAwareSentimentAnalyzer()


def analyze_sentiment_enhanced(text: str, conversation_id: Optional[UUID] = None,
                               user_id: Optional[UUID] = None) -> Dict:
    """
    Convenience function for enhanced sentiment analysis.
    
    Args:
        text: Text to analyze
        conversation_id: Optional conversation ID for context
        user_id: Optional user ID
        
    Returns:
        Enhanced sentiment analysis result
    """
    return _enhanced_analyzer.analyze(text, conversation_id, user_id)


def get_conversation_summary(conversation_id: UUID) -> Dict:
    """Get conversation sentiment summary."""
    return _enhanced_analyzer.get_conversation_sentiment_summary(conversation_id)
