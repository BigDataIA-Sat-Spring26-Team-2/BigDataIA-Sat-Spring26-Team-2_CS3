# app/pipelines/say_score_analyzer.py

import math
import re
from typing import List
from app.services.snowflake import get_connection
from app.config import get_settings

class SayScoreAnalyzer:
    """Calculate AI claim intensity from SEC filings"""
    
    AI_KEYWORDS = [
        # Core AI Terms
        "artificial intelligence",
        r"\bAI\b",
        "machine learning",
        r"\bML\b",
        "deep learning",
        "neural network",
        "neural networks",
        
        # AI Subdisciplines
        "natural language processing",
        r"\bNLP\b",
        "computer vision",
        "speech recognition",
        "image recognition",
        "pattern recognition",
        "reinforcement learning",
        "supervised learning",
        "unsupervised learning",
        "transfer learning",
        
        # Generative AI / LLMs
        "generative AI",
        "generative artificial intelligence",
        "large language model",
        r"\bLLM\b",
        r"\bLLMs\b",
        "foundation model",
        "transformer",
        "transformers",
        "GPT",
        "chatbot",
        "conversational AI",
        
        # ML/AI Infrastructure
        "machine learning platform",
        "ML platform",
        "AI platform",
        "MLOps",
        "model training",
        "model deployment",
        "inference",
        "AI infrastructure",
        
        # Data Science & Analytics
        "data science",
        "predictive analytics",
        "predictive modeling",
        "statistical modeling",
        "data mining",
        "big data analytics",
        
        # AI Applications
        r"\bAI-powered\b",
        r"\bAI-driven\b",
        r"\bAI-enabled\b",
        r"\bAI-based\b",
        "intelligent automation",
        "cognitive computing",
        "intelligent systems",
        "recommendation engine",
        "recommendation system",
        "personalization engine",
        "fraud detection",
        "anomaly detection",
        "sentiment analysis",
        
        # Automation & Robotics
        "robotic process automation",
        r"\bRPA\b",
        "automation",
        "intelligent automation",
        "autonomous",
        "robotics",
        
        # Algorithms
        "algorithm",
        "algorithms",
        "decision tree",
        "random forest",
        "gradient boosting",
        "support vector machine",
        r"\bSVM\b",
        "k-means",
        "clustering",
        "classification",
        "regression",
        
        # Specific Technologies
        "TensorFlow",
        "PyTorch",
        "scikit-learn",
        "Keras",
        "OpenAI",
        "Anthropic",
        "Hugging Face",
        "Azure AI",
        "AWS AI",
        "Google AI",
        "SageMaker",
        
        # Business/Strategy Terms
        "AI strategy",
        "AI initiative",
        "AI investment",
        "AI transformation",
        "digital transformation",
        "AI adoption",
        "AI capability",
        "AI capabilities",
        "AI solution",
        "AI technology",
        "AI tools",
        
        # Emerging/Trending
        "edge AI",
        "federated learning",
        "explainable AI",
        r"\bXAI\b",
        "responsible AI",
        "AI ethics",
        "AI governance",
        "synthetic data",
        "data augmentation",
        "prompt engineering",
        "fine-tuning",
        "vector database",
        "embeddings",
        "semantic search",
        
        # Industry-Specific
        "AI-assisted",
        "AI model",
        "AI models",
        "intelligent agent",
        "virtual assistant",
        "voice assistant",
        "AI copilot",
    ]
    
    # Optional: Categorize keywords for weighted scoring
    KEYWORD_WEIGHTS = {
        # High-value strategic terms (1.5x weight)
        "AI strategy": 1.5,
        "AI transformation": 1.5,
        "AI investment": 1.5,
        "AI initiative": 1.5,
        "generative AI": 1.5,
        "large language model": 1.5,
        
        # Core AI terms (1.0x weight - default)
        # Most keywords fall here
        
        # Generic/buzzword terms (0.5x weight)
        "automation": 0.5,
        "digital transformation": 0.5,
        "algorithm": 0.5,
        "algorithms": 0.5,
    }
    
    def calculate_say_score(self, ticker: str) -> float:
        """Calculate Say Score for a company based on SEC filings"""
        chunks = self._get_company_chunks(ticker)
        
        if not chunks:
            print(f"  ⚠️  No chunks found for {ticker}")
            return 0.0
        
        all_text = " ".join(chunks)
        total_words = len(all_text.split())
        
        if total_words == 0:
            return 0.0
        
        # Count weighted keyword mentions
        total_mentions = 0
        weighted_mentions = 0.0
        
        for keyword in self.AI_KEYWORDS:
            if r"\b" in keyword:  # Regex pattern
                matches = re.findall(keyword, all_text, re.IGNORECASE)
                count = len(matches)
            else:  # Simple string
                count = all_text.lower().count(keyword.lower())
            
            if count > 0:
                total_mentions += count
                # Apply weight if defined, otherwise 1.0
                weight = self.KEYWORD_WEIGHTS.get(keyword, 1.0)
                weighted_mentions += count * weight
        
        # Calculate density (mentions per 1000 words)
        mention_density = (weighted_mentions / total_words) * 1000
        
        # Convert to 0-100 scale
        # Benchmark: 1 weighted mentions per 1000 words = 100 points
        import math
        raw_score = min(math.sqrt(mention_density) * 95, 100)
        
        print(f"  📊 {ticker}: {total_words:,} words, {total_mentions} mentions ({weighted_mentions:.1f} weighted), density={mention_density:.2f}, score={raw_score:.1f}")
        
        return round(raw_score, 1)
    
    def _get_company_chunks(self, ticker: str) -> List[str]:
        """Get ALL document chunks for a company"""
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            query = f"""
            SELECT dc.chunk_text
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
            JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                ON dc.document_id = d.id
            WHERE d.ticker = %s
                AND d.filing_type IN ('10-K', '10-Q', '8-K','DEF 14A')
            ORDER BY d.filing_date DESC, dc.chunk_index
            """
            
            cur.execute(query, (ticker,))
            rows = cur.fetchall()
            
            chunks = [row[0] for row in rows if row[0]]
            print(f"  📄 {ticker}: Found {len(chunks)} chunks")
            
            return chunks
            
        finally:
            cur.close()
            conn.close()