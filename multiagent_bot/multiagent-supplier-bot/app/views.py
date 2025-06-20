import logging
import json

from flask import Blueprint, request, jsonify, current_app

from .decorators.security import signature_required
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,
)

webhook_blueprint = Blueprint("webhook", __name__)


def handle_message():
    """
    Handle incoming webhook events from the WhatsApp API.

    This function processes incoming WhatsApp messages and other events,
    such as delivery statuses. If the event is a valid message, it gets
    processed. If the incoming payload is not a recognized WhatsApp event,
    an error is returned.

    Every message send will trigger 4 HTTP requests to your webhook: message, sent, delivered, read.

    Returns:
        response: A tuple containing a JSON response and an HTTP status code.
    """
    body = request.get_json()
    logging.info(f"Received webhook event type: {body.get('object')}")

    # Check if it's a WhatsApp status update
    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("statuses")
    ):
        statuses = body["entry"][0]["changes"][0]["value"]["statuses"]
        for status in statuses:
            status_type = status.get("status")
            message_id = status.get("id")
            recipient_id = status.get("recipient_id")
            timestamp = status.get("timestamp")
            logging.info(f"Status Update: {status_type}, Message ID: {message_id}, Recipient: {recipient_id}, Time: {timestamp}")
        return jsonify({"status": "ok"}), 200

    # Check if it's a message event
    if (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("messages")
    ):
        try:
            if is_valid_whatsapp_message(body):
                process_whatsapp_message(body)
                return jsonify({"status": "ok"}), 200
            else:
                logging.warning("Invalid WhatsApp message format")
                return (
                    jsonify({"status": "error", "message": "Invalid message format"}),
                    400,
                )
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON")
            return jsonify({"status": "error", "message": "Invalid JSON provided"}), 400
        except Exception as e:
            logging.error(f"Error processing message: {str(e)}")
            return jsonify({"status": "error", "message": "Internal server error"}), 500

    # If we get here, it's an unrecognized event type
    logging.warning(f"Unrecognized event type: {body}")
    return jsonify({"status": "error", "message": "Unrecognized event type"}), 400


# Required webhook verifictaion for WhatsApp
def verify():
    # Parse params from the webhook verification request
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == current_app.config["VERIFY_TOKEN"]:
            # Respond with 200 OK and challenge token from the request
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logging.info("VERIFICATION_FAILED")
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logging.info("MISSING_PARAMETER")
        return jsonify({"status": "error", "message": "Missing parameters"}), 400


@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required
def webhook_post():
    return handle_message()


