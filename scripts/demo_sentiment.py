"""Demo script to showcase enhanced sentiment analysis for HR visibility."""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.services.sentiment_enhanced import analyze_sentiment_enhanced, get_conversation_summary
from uuid import uuid4


def demo_enhanced_sentiment():
    """Demonstrate enhanced sentiment analysis features."""
    
    print("=" * 70)
    print("MARK Enhanced Sentiment Analysis Demo")
    print("=" * 70)
    
    # Test cases representing real employee messages
    test_messages = [
        # Positive sentiments
        ("I'm thrilled about the new wellness program! 😊", "positive"),
        ("Thank you so much for the quick support! ❤️", "positive"),
        ("Great work on the project! Really appreciate it.", "positive"),
        
        # Negative sentiments  
        ("I'm completely burned out and exhausted", "negative"),
        ("This micromanagement is making me miserable", "negative"),
        ("The toxic culture here needs to change", "negative"),
        
        # Sarcasm detection
        ("Oh great, another deadline moved up. Just what I needed!", "sarcastic"),
        ("Yeah sure, working weekends again is exactly what I wanted.", "sarcastic"),
        
        # Context-dependent
        ("I'm feeling overwhelmed", "context_demo"),
        ("But I got promoted today!", "context_demo"),
        ("Still stressed about the workload though", "context_demo"),
        
        # Neutral
        ("The meeting is scheduled for 3 PM tomorrow", "neutral"),
    ]
    
    conversation_id = uuid4()
    
    for message, category in test_messages:
        print(f"\n{'─' * 70}")
        print(f"Category: {category.upper()}")
        print(f"Message: \"{message}\"")
        print(f"{'─' * 70}")
        
        if category == "context_demo":
            result = analyze_sentiment_enhanced(message, conversation_id=conversation_id)
        else:
            result = analyze_sentiment_enhanced(message)
        
        print(f"Sentiment: {result['sentiment'].upper()} (score: {result['score']})")
        print(f"Intensity: {result['intensity']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Primary Emotion: {result['emotions']['primary']}")
        
        if result['sarcasm']['detected']:
            print(f"⚠️  SARCASM DETECTED (confidence: {result['sarcasm']['confidence']})")
        
        if result.get('context_adjusted'):
            print(f"📝 Context-adjusted from {result['original_score']} to {result['score']}")
    
    # Show conversation summary
    print(f"\n{'=' * 70}")
    print("Conversation Summary")
    print(f"{'=' * 70}")
    summary = get_conversation_summary(conversation_id)
    print(f"Total messages: {summary['message_count']}")
    print(f"Average sentiment: {summary['average_score']:.2f}")
    print(f"Dominant sentiment: {summary['dominant_sentiment']}")
    print(f"Trend: {summary['trend']}")
    
    print(f"\n{'=' * 70}")
    print("HR Dashboard Integration")
    print(f"{'=' * 70}")
    print("✅ Employee sentiments are automatically logged to sentiment_logs table")
    print("✅ HR can view real-time sentiment scores on the dashboard")
    print("✅ Risk scores are calculated based on negative sentiment patterns")
    print("✅ Alerts trigger when sustained negative sentiment is detected")
    print("✅ Enhanced features: sarcasm detection, emotion analysis, context awareness")
    

if __name__ == "__main__":
    demo_enhanced_sentiment()
