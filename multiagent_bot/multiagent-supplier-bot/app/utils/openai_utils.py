import logging
import openai
from flask import current_app

def call_openai_chat(messages, temperature=0.3):
    """
    Make a call to OpenAI Chat Completion API
    """
    try:
        client = openai.OpenAI(api_key=current_app.config['OPENAI_API_KEY'])
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # You can change this to your preferred model
            messages=messages,
            temperature=temperature,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API error: {e}")
        return None