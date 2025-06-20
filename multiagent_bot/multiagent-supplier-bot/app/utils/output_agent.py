import json
from .openai_utils import call_openai_chat

class OutputAgent:
    """
    Agent that formats and sends the final response
    """
    
    def __init__(self):
        self.system_prompt = """
        You are an output formatting agent for the price management system. Your job is to:
        1. Format responses from other agents for WhatsApp
        2. Make responses friendly and professional
        3. Handle error cases gracefully
        4. Ask for clarification when needed
        
        Keep responses concise but informative. Use emojis sparingly and appropriately.
        Respond in English as users communicate in English.
        """
    
    def format_response(self, agent_response, query_analysis, original_message):
        """
        Format the final response for WhatsApp
        """
        if query_analysis.get("intent") == "unclear" or query_analysis.get("clarification_needed"):
            return self.format_clarification_request(query_analysis, original_message)
        
        return self.format_success_response(agent_response, query_analysis)
    
    def format_clarification_request(self, query_analysis, original_message):
        """
        Format a request for clarification
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""
            User sent: "{original_message}"
            Analysis result: {json.dumps(query_analysis)}
            
            Create a friendly response that asks for missing information to help with price update or discount request.
            Respond in English.
            """}
        ]
        
        response = call_openai_chat(messages)
        return response or "I need more information to help you. Please provide the product ID and new price or discount amount."
    
    def format_success_response(self, api_response, query_analysis):
        """
        Format a successful operation response
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""
            API Response: {api_response}
            Original request was: {query_analysis.get('intent')} for product {query_analysis.get('product_id')}
            
            Create a friendly confirmation message for the user.
            Respond in English.
            """}
        ]
        
        response = call_openai_chat(messages)
        return response or f"Operation completed successfully for product {query_analysis.get('product_id')}. ✅"