import logging
from .dummy_functions import increase_price, decrease_price, discount

class PriceManagementAgent:    
    """
    Agent that handles price increases, decreases, and discounts
    """
    
    def __init__(self):
        self.system_prompt = """
        You are a price management agent. You handle price increases, decreases, and discounts for products.
        When you receive a request, you will call the appropriate API and return the result.
        Keep your responses brief and professional.
        """
    
    def normalize_product_id(self, product_id):
        """
        Normalize product ID to uppercase to match database format
        """
        if product_id:
            return str(product_id).upper().strip()
        return product_id
    
    def increase_price(self, product_id, new_price):
        """
        Call the price increase API
        """
        try:
            normalized_product_id = self.normalize_product_id(product_id)
            return increase_price(normalized_product_id, new_price)
        except Exception as e:
            logging.error(f"Price increase API error: {e}")
            return f"Error increasing price for product {product_id}: {str(e)}"
    
    def decrease_price(self, product_id, new_price):
        """
        Call the price decrease API
        """
        try:
            normalized_product_id = self.normalize_product_id(product_id)
            return decrease_price(normalized_product_id, new_price)
        except Exception as e:
            logging.error(f"Price decrease API error: {e}")
            return f"Error decreasing price for product {product_id}: {str(e)}"
    
    def apply_discount(self, product_id, discount_amount):
        """
        Call the discount API
        """
        try:
            normalized_product_id = self.normalize_product_id(product_id)
            return discount(normalized_product_id, discount_amount)
        except Exception as e:
            logging.error(f"Discount API error: {e}")
            return f"Error applying discount to product {product_id}: {str(e)}"
    
    def process_request(self, intent, product_id, amount):
        """
        Process the price management request
        """
        if intent == "price_increase":
            return self.increase_price(product_id, amount)
        elif intent == "price_decrease":
            return self.decrease_price(product_id, amount)
        elif intent == "discount":
            return self.apply_discount(product_id, amount)
        else:
            return "Invalid request type. I can only handle price increases, decreases, and discounts."