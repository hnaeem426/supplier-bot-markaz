import logging
from flask import current_app, jsonify
import json
import requests
import re
import time
from datetime import datetime, timedelta
from .openai_utils import call_openai_chat
from .query_identifier_agent import QueryIdentifierAgent
from .price_management_agent import PriceManagementAgent
from .output_agent import OutputAgent

# Dictionary to track recent function calls to prevent duplicates
_recent_function_calls = {}
# How long to remember a function call (in seconds)
_function_call_expiry = 60  

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )
        response.raise_for_status()
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        log_http_response(response)
        return response

def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text

# Store user conversation threads
user_conversation_threads = {}

# Track processed message IDs to prevent duplicates
processed_message_ids = set()

def is_message_processed(message_id):
    """
    Check if a message has already been processed
    """
    if message_id in processed_message_ids:
        return True
    processed_message_ids.add(message_id)
    return False

def get_conversation_history(wa_id, limit=10):
    """
    Get recent conversation history for context
    """
    if wa_id not in user_conversation_threads:
        user_conversation_threads[wa_id] = []
    
    return user_conversation_threads[wa_id][-limit:]

def add_to_conversation_history(wa_id, role, content):
    """
    Add message to conversation history
    """
    if wa_id not in user_conversation_threads:
        user_conversation_threads[wa_id] = []
    
    user_conversation_threads[wa_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now()
    })
    
    # Keep only last 50 messages to prevent memory issues
    if len(user_conversation_threads[wa_id]) > 50:
        user_conversation_threads[wa_id] = user_conversation_threads[wa_id][-50:]

def generate_response(message_body, wa_id=None, name=None):
    """
    Generate a response using the multi-agent system
    """
    try:
        # Add user message to conversation history
        add_to_conversation_history(wa_id, "user", message_body)
        
        # Get conversation history for context
        conversation_history = get_conversation_history(wa_id)
        
        # Initialize agents
        query_agent = QueryIdentifierAgent()
        price_agent = PriceManagementAgent()
        output_agent = OutputAgent()
        
        # Step 1: Analyze the query
        logging.info("Step 1: Analyzing query with Query Identifier Agent")
        query_analysis = query_agent.analyze_query(message_body, conversation_history)
        logging.info(f"Query analysis result: {query_analysis}")
        
        # Step 2: Process the request if clear, otherwise ask for clarification
        if query_analysis.get("intent") in ["price_increase", "price_decrease", "discount"] and \
           query_analysis.get("product_id") and query_analysis.get("amount"):
            
            logging.info("Step 2: Processing request with Price Management Agent")
            api_response = price_agent.process_request(
                query_analysis["intent"],
                query_analysis["product_id"],
                query_analysis["amount"]
            )
            logging.info(f"Price agent response: {api_response}")
        else:
            api_response = None
            logging.info("Step 2: Skipped - clarification needed")
        
        # Step 3: Format the response
        logging.info("Step 3: Formatting response with Output Agent")
        final_response = output_agent.format_response(api_response, query_analysis, message_body)
        
        # Add assistant response to conversation history
        add_to_conversation_history(wa_id, "assistant", final_response)
        
        return final_response
        
    except Exception as e:
        logging.error(f"Error in multi-agent response generation: {e}")
        return "There was some problem while processing your request. Kindly try again."

def process_whatsapp_message(body):
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_id = message.get("id")
    
    # Skip if message already processed
    if is_message_processed(message_id):
        logging.info(f"Skipping already processed message: {message_id}")
        return
        
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
    message_body = message["text"]["body"]

    # Generate response using the multi-agent system
    response = generate_response(message_body, wa_id, name)
    response = process_text_for_whatsapp(response)

    data = get_text_message_input(wa_id, response)
    send_message(data)

def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )