import logging
import json
from .openai_utils import call_openai_chat

class QueryIdentifierAgent:
    """
    Agent that identifies the context and intent from user messages
    """
    
    def __init__(self):
        self.system_prompt = """
        You are a query identifier agent for the Markaz Supplier System. Your job is to analyze supplier messages and determine:
        1. If the supplier wants to increase product price (increase)
        2. If the supplier wants to decrease product price (decrease)
        3. If the supplier wants to apply discount to a product
        4. Extract product ID and price/discount amount if mentioned
        
        Always respond in JSON format:
        {
            "intent": "price_increase" or "price_decrease" or "discount" or "unclear",
            "product_id": "extracted product ID or null",
            "amount": "extracted price/discount amount or null",
            "confidence": "high" or "medium" or "low",
            "clarification_needed": "what information is missing if any"
        }
        
        Examples of user messages:
        - "ABC123 ki price 50 kar do" -> price increase
        - "XYZ789 ki qeemat barha do 100" -> price increase
        - "product DEF456 kam kar do price 30" -> price decrease
        - "GHI789 pe 20% discount laga do" -> discount
        - "price kam karni hai" -> unclear, product ID and amount needed
        - "qeemat barha dou" -> unclear, product ID and amount needed
        - "discount lagana hai" -> unclear, product ID and amount needed
        
        Understand Urdu/Hindi words:
        - "barha do", "barha dou", "increase kar do" = price_increase
        - "kam kar do", "kam karo", "decrease kar do" = price_decrease
        - "discount laga do", "discount lagao" = discount
        """
    
    def normalize_product_id(self, product_id):
        """
        Normalize product ID to uppercase to match database format
        """
        if product_id:
            return str(product_id).upper().strip()
        return product_id
    
    def analyze_query(self, user_message, conversation_history):
        # Build context from conversation history
        context_messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add recent conversation for context
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            context_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        context_messages.append({
            "role": "user", 
            "content": user_message
        })
        
        response = call_openai_chat(context_messages)
        
        try:
            result = json.loads(response)
            # Normalize product ID to uppercase
            if result.get("product_id"):
                result["product_id"] = self.normalize_product_id(result["product_id"])
            return result
        except json.JSONDecodeError:
            logging.error(f"Failed to parse query identifier response: {response}")
            return {
                "intent": "unclear",
                "product_id": None,
                "amount": None,
                "confidence": "low",
                "clarification_needed": "Failed to understand the request"
            }