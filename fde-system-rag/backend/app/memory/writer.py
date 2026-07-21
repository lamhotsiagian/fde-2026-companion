import json
import logging
from uuid import UUID
from datetime import datetime
from langchain.chat_models import init_chat_model
from app.config import settings

logger = logging.getLogger(__name__)

async def extract_memories(conversation_turns: list, model_name: str) -> list[dict]:
    """
    Extracts structured memory units (episodic facts, user preferences/procedural, or entity relations)
    from a list of message turns using an LLM.
    (Chapter 4: Memory Write Path - Extraction)
    """
    try:
        from app.chat.langgraph_agent import create_model
        model = create_model(model_name=model_name)
        
        conversation_str = ""
        for msg in conversation_turns:
            role = "User" if msg.type == "human" else "Assistant"
            conversation_str += f"{role}: {msg.content}\n"
            
        system_instructions = (
            "You are an expert memory extraction sub-system. Analyze the conversation history "
            "and extract key memory items. Each memory item MUST fit one of these categories:\n"
            "- episodic: Specific events or statements made by the user (\"User mentioned they attended a conference on June 20\").\n"
            "- semantic: Stable factual information about the user or their preferences (\"User prefers Python over Java\", \"User lives in Boston\").\n"
            "- procedural: Workflows, guidelines, or interactive preferences (\"User wants summaries formatted in markdown tables\").\n"
            "- entity: Structured facts about a person, place, or specific object (\"Google DeepMind is an AI research lab\").\n\n"
            "Return a valid JSON array of objects, where each object has:\n"
            "1. 'memory_type': one of [episodic, semantic, procedural, entity]\n"
            "2. 'content': brief factual summary (under 200 characters)\n"
            "3. 'importance_score': a float between 0.0 and 1.0 showing how critical or permanent it is to remember this (e.g. core preferences = 0.9, casual statements = 0.3)\n"
            "4. 'metadata': an object containing supporting properties (e.g. name of the entity, date reference, etc.)\n\n"
            "Reply ONLY with the JSON array. Do not include markdown code block formatting or explanation."
        )
        
        prompt = f"{system_instructions}\n\nConversation:\n{conversation_str}\n\nJSON output:"
        response = await model.ainvoke(prompt)
        text = response.content.strip()
        
        # Clean potential markdown wrapping
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        extracted = json.loads(text)
        if isinstance(extracted, list):
            return extracted
        return []
    except Exception as e:
        logger.error(f"Failed to extract memories: {str(e)}")
        return []

def calculate_importance(content: str) -> float:
    """
    Fallback deterministic salience scoring mechanism based on keyword heuristics.
    """
    content_lower = content.lower()
    score = 0.3
    # Check key signals
    high_priority = ["prefer", "always", "never", "hate", "love", "remember", "must", "work as", "live in"]
    medium_priority = ["like", "know", "study", "use", "want", "client", "project"]
    
    for kw in high_priority:
        if kw in content_lower:
            score = max(score, 0.8)
    for kw in medium_priority:
        if kw in content_lower:
            score = max(score, 0.6)
            
    return score

def apply_relevance_decay(created_at: datetime, decay_rate: float) -> float:
    """
    Calculates relevance/decay using the Ebbinghaus forgetting curve formula:
    R = e^(-d * t)
    where d is the decay rate and t is time delta in days.
    (Chapter 4: Forgetting curves & relevance decay)
    """
    import math
    delta = datetime.now() - created_at
    t_days = max(delta.total_seconds() / (24 * 3600), 0.0)
    relevance = math.exp(-decay_rate * t_days)
    return max(relevance, 0.0)
