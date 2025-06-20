"""
Function handlers for OpenAI Assistant API function calls
"""
import logging
import requests
from flask import current_app
import datetime
import json
import os

# Dictionary to store price increase attempts
_price_increase_log = {}
_PRICE_LOG_FILE = "price_increase_log.json"

def load_price_log():
    """Load price increase log from file"""
    try:
        if os.path.exists(_PRICE_LOG_FILE):
            with open(_PRICE_LOG_FILE, 'r') as f:
                data = json.load(f)
                logging.info(f"Loaded price log with {len(data)} entries")
                return data
        logging.info("No existing price log file found")
        return {}
    except Exception as e:
        logging.error(f"Error loading price log: {e}")
        return {}

def save_price_log():
    """Save price increase log to file"""
    try:
        with open(_PRICE_LOG_FILE, 'w') as f:
            json.dump(_price_increase_log, f, indent=2)
        logging.info(f"Price log saved with {len(_price_increase_log)} entries")
    except Exception as e:
        logging.error(f"Error saving price log: {e}")

# Load existing log on startup
_price_increase_log = load_price_log()

def check_product_listing(business_name, product_id):
    """
    Check if a product is listed for a specific business

    Args:
        business_name (str): Name of the business
        product_id (str): ID of the product to check

    Returns:
        str: Message indicating whether the product is listed or not
    """
    logging.info(f"Checking product {product_id} for business {business_name}")
        
    if product_id.startswith("PROD"):
        return f"✅ Product `{product_id}` for business *{business_name}* is listed."
    else:
        return f"❌ Product `{product_id}` not found for *{business_name}*."
    
def cancellation_of_orders(order_item_id, reason="FakeOrders/Non-deliverable orders", status_by="CS Team"):
    """
    Cancel an order using the Markaz API

    Args:
        order_item_id (str or int): The ID of the order item to cancel
        reason (str, optional): Reason for cancellation. Defaults to "FakeOrders/Non-deliverable orders".
        status_by (str, optional): Who requested the cancellation. Defaults to "CS Team".

    Returns:
        str: Message indicating whether the order was successfully cancelled
    """
    logging.info(f"Cancelling order {order_item_id}")

    url = "https://api.markaz.app/shipping/markaz/order/status"
    

    # Request payload - explicitly convert orderItemId to string
    payload = [{
        "orderItemId": str(order_item_id),  # Explicitly convert to string
        "trackingId": "",
        "status": "Cancelled",
        "statusBy": status_by,
        "reason": reason
    }]

    headers = {
        "Content-Type": "application/json",
        # Get the token from environment variables
        "Authorization": f"Bearer {current_app.config['MARKAZ_AUTH_TOKEN']}"
    }

    try:
        # Print payload for debugging
        logging.info(f"Sending request to URL: {url}")
        logging.info(f"Sending payload: {payload}")
        logging.info(f"Using token: {current_app.config.get('MARKAZ_AUTH_TOKEN')}")
        
        response = requests.put(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            logging.info(f"Successfully cancelled order {order_item_id}")
            return f"✅ Order `{order_item_id}` has been successfully cancelled."
        else:
            # Log response details for debugging
            logging.error(f"Failed to cancel order {order_item_id}. Status code: {response.status_code}")
            logging.error(f"Response text: {response.text}")
            return f"❌ Failed to cancel order `{order_item_id}`. API responded with status code {response.status_code}."

    except Exception as e:
        logging.error(f"Error cancelling order {order_item_id}: {str(e)}")
        return f"❌ Error occurred while trying to cancel order `{order_item_id}`: {str(e)}"

def has_recent_increase(product_id):
    """
    Check if a product has had a price increase in the last week
    
    Args:
        product_id (str): The product ID to check
        
    Returns:
        bool: True if there was a recent increase, False otherwise
    """
    if product_id not in _price_increase_log:
        return False
        
    last_increase = datetime.datetime.fromisoformat(_price_increase_log[product_id])
    one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    
    return last_increase >= one_week_ago

def log_price_increase(product_id):
    """Log a price increase attempt for a product"""
    try:
        _price_increase_log[product_id] = datetime.datetime.now().isoformat()
        logging.info(f"Logging price increase for product {product_id} at {_price_increase_log[product_id]}")
        save_price_log()
        logging.info(f"Successfully saved price increase log to {_PRICE_LOG_FILE}")
    except Exception as e:
        logging.error(f"Failed to log price increase: {str(e)}")

def update_price(product_id, new_price):
    """
    Updates the price for a product.
    - Fetches old price from API.
    - If price is increasing, applies a 10% limit check.
    - If price is decreasing or unchanged, updates directly.
    """
    base_url = "https://script.google.com/macros/s/AKfycbxRdURlwCEQ_OTJyBKIY5nRJ9Npty7XxIEvarjjzXQxBfHwtNFBTOjDGSkdx5LtiMhl/exec"

    logging.info(f"Attempting to update price for product {product_id} to {new_price}")

    try:
        # === Step 1: Get current price ===
        get_params = {"supplierproductcode": str(product_id)}
        get_response = requests.get(base_url, params=get_params)

        logging.info(f"Response from API for product {product_id}: {get_response.text}")

        if get_response.status_code != 200:
            raise Exception(f"Failed to retrieve current price. Status: {get_response.status_code}, Response: {get_response.text}")

        data = get_response.json()
        price_from_sheet = float(data.get("update_price", 0))
        logging.info(f"Retrieved current price for {product_id}: {price_from_sheet}")
        oldPrice_from_sheet = float(data.get("update_oldPrice", 0))
        logging.info(f"Retrieved oldprice for {product_id}: {oldPrice_from_sheet}")
        shippingCharges_from_sheet = float(data.get("update_additionalshippingcharges", 0))
        logging.info(f"Retrieved additional shipping charges for {product_id}: {shippingCharges_from_sheet}")

        updated_price = new_price - shippingCharges_from_sheet

        # Initialize payload with common fields
        payload = {
            "supplierproductcode": str(product_id),
            "new_price": updated_price
        }

        # === Step 2: Determine type of change ===
        if new_price > oldPrice_from_sheet:
            # Check for recent price increase
            if has_recent_increase(product_id):
                return f"⚠️ Price increase for product `{product_id}` was attempted within the last week. Please wait before increasing the price again."
            
            increase_percent = ((new_price - oldPrice_from_sheet) / oldPrice_from_sheet) * 100
            if increase_percent > 10:
                return f"⚠️ Price increase of {increase_percent:.2f}% exceeds 10% threshold. Update rejected for product `{product_id}`."
            
            change_type = "increased"
            payload["old_price"] = max(new_price, oldPrice_from_sheet)
            # Log the price increase
            log_price_increase(product_id)

        elif new_price < oldPrice_from_sheet:
            change_type = "decreased"
            payload["old_price"] = new_price  

        else:
            change_type = "unchanged"
            payload["old_price"] = oldPrice_from_sheet  # Keep old price if unchanged

        logging.info(f"Sending POST request with payload: {payload}")

        post_response = requests.post(base_url, json=payload)

        if post_response.status_code != 200:
            raise Exception(f"Failed to update price. Status: {post_response.status_code}, Response: {post_response.text}")

        return f"✅ Price for product `{product_id}` will be {change_type} from {price_from_sheet} to {updated_price} soon."

    except Exception as e:
        logging.error(f"Error updating price for product {product_id}: {str(e)}")
        return f"❌ Error occurred while updating price for product `{product_id}`: {str(e)}"


def discount(product_id, new_price):
    """right 
    Updates the price for a product.
    - Changes the price only.
    - Keeps the old price.
    """
    base_url = "https://script.google.com/macros/s/AKfycby9s68FArBBMxrzVcbsaS3xDQ9orMBOOGfZMjD_r0yB7aDySdKzkzthEcoAWNIJj7aS/exec"

    logging.info(f"Applying discount by changing price for product {product_id} to {new_price}")

    try:
        # === Step 1: Get current price ===
        get_params = {"supplierproductcode": str(product_id)}
        get_response = requests.get(base_url, params=get_params)

        logging.info(f"Response from API for product {product_id}: {get_response.text}")

        if get_response.status_code != 200:
            raise Exception(f"Failed to retrieve current price. Status: {get_response.status_code}, Response: {get_response.text}")

        data = get_response.json()
        price_from_sheet = float(data.get("update_price", 0))
        logging.info(f"Retrieved current price for {product_id}: {price_from_sheet}")
        oldPrice_from_sheet = float(data.get("update_oldPrice", 0))
        logging.info(f"Retrieved oldprice for {product_id}: {oldPrice_from_sheet}")
        shippingCharges_from_sheet = float(data.get("update_additionalshippingcharges", 0))
        logging.info(f"Retrieved additional shipping charges for {product_id}: {shippingCharges_from_sheet}")

        # === Step 2: Check if new price exceeds old price ===
        if new_price > oldPrice_from_sheet:
            return f"⚠️ Discounted price cannot exceed old price. Update rejected for product `{product_id}`."
        
        else:
            new_price = new_price - shippingCharges_from_sheet

        # === Step 3: Post new price ===
        payload = {
            "supplierproductcode": str(product_id),
            "new_price": new_price,
            "old_price" : oldPrice_from_sheet  # Keep old price unchanged   
        }

        post_response = requests.post(base_url, json=payload)

        if post_response.status_code != 200:
            raise Exception(f"Failed to update price. Status: {post_response.status_code}, Response: {post_response.text}")

        return f"✅ Discount applied for product `{product_id}`. Price changed from {oldPrice_from_sheet} to {new_price} with additional shipping charges {shippingCharges_from_sheet}."

    except Exception as e:
        logging.error(f"Error updating price for product {product_id}: {str(e)}")
        return f"❌ Error occurred while updating price for product `{product_id}`: {str(e)}"