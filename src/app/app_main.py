"""
Flask application for ECS service
Handles API requests and orchestrates order processing
"""

import json
import logging
import os
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Tuple

import boto3
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize AWS clients
sqs_client = boto3.client("sqs")
sfn_client = boto3.client("stepfunctions")
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
PROJECT_NAME = os.getenv("PROJECT_NAME", "my-app")
ORDERS_QUEUE_URL = os.getenv("ORDERS_QUEUE_URL", "")
STATE_MACHINE_ARN = os.getenv("STATE_MACHINE_ARN", "")
ORDERS_TABLE = f"{PROJECT_NAME}-orders-{ENVIRONMENT}"

# DynamoDB table
orders_table = dynamodb.Table(ORDERS_TABLE)


def require_auth(f):
    """Decorator to require API key authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")

        if not api_key or api_key != os.getenv("API_KEY", ""):
            logger.warning(f"Unauthorized request from {request.remote_addr}")
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated_function


def log_request():
    """Log incoming request"""
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")


def record_metric(metric_name: str, value: float = 1, unit: str = "Count") -> None:
    """Record metric to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace=f"{PROJECT_NAME}/{ENVIRONMENT}",
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Timestamp": datetime.utcnow(),
                }
            ],
        )
    except Exception as e:
        logger.error(f"Failed to record metric: {str(e)}")


# ===== HEALTH CHECK ENDPOINTS =====


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    try:
        # Check basic connectivity
        status = "healthy"

        # Try to access DynamoDB
        try:
            orders_table.table_status
            dynamodb_status = "ok"
        except Exception as e:
            logger.warning(f"DynamoDB check failed: {str(e)}")
            dynamodb_status = "degraded"
            status = "degraded" if status == "healthy" else status

        # Try to check SQS
        try:
            sqs_client.get_queue_attributes(
                QueueUrl=ORDERS_QUEUE_URL, AttributeNames=["ApproximateNumberOfMessages"]
            )
            sqs_status = "ok"
        except Exception as e:
            logger.warning(f"SQS check failed: {str(e)}")
            sqs_status = "degraded"
            status = "degraded"

        return (
            jsonify(
                {
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    "checks": {"dynamodb": dynamodb_status, "sqs": sqs_status},
                    "environment": ENVIRONMENT,
                    "version": "1.0.0",
                }
            ),
            200 if status == "healthy" else 503,
        )

    except Exception as e:
        logger.exception(f"Health check failed: {str(e)}")
        return (
            jsonify(
                {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
            ),
            500,
        )


@app.route("/live", methods=["GET"])
def liveness():
    """Kubernetes liveness probe"""
    return jsonify({"status": "alive"}), 200


@app.route("/ready", methods=["GET"])
def readiness():
    """Kubernetes readiness probe"""
    try:
        # Check if service is ready to accept requests
        orders_table.table_status
        return jsonify({"status": "ready"}), 200
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return jsonify({"status": "not_ready", "error": str(e)}), 503


# ===== ORDER ENDPOINTS =====


@app.route("/api/orders", methods=["POST"])
@require_auth
def create_order() -> Tuple[Dict[str, Any], int]:
    """
    Create a new order

    Expected JSON:
    {
        "customer_id": "string",
        "items": [...],
        "shipping_address": {...}
    }
    """
    log_request()

    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["customer_id", "items"]
        if not all(field in data for field in required_fields):
            logger.warning(f"Missing required fields: {data}")
            return jsonify({"error": "Missing required fields"}), 400

        # Generate order ID
        order_id = f"ORD-{datetime.utcnow().timestamp()}"

        # Create order object
        order = {
            "order_id": order_id,
            "customer_id": data["customer_id"],
            "items": data["items"],
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "environment": ENVIRONMENT,
        }

        # Save to DynamoDB
        orders_table.put_item(Item=order)
        logger.info(f"Order created: {order_id}")

        # Send to SQS for processing
        sqs_client.send_message(QueueUrl=ORDERS_QUEUE_URL, MessageBody=json.dumps(order))

        # Record metric
        record_metric("OrderCreated")

        return (
            jsonify(
                {
                    "order_id": order_id,
                    "status": "created",
                    "message": "Order received and queued for processing",
                }
            ),
            201,
        )

    except Exception as e:
        logger.exception(f"Error creating order: {str(e)}")
        record_metric("OrderCreationError")
        return jsonify({"error": str(e)}), 500


@app.route("/api/orders/<order_id>", methods=["GET"])
@require_auth
def get_order(order_id: str) -> Tuple[Dict[str, Any], int]:
    """Get order details"""
    log_request()

    try:
        response = orders_table.get_item(Key={"order_id": order_id})

        if "Item" not in response:
            logger.warning(f"Order not found: {order_id}")
            return jsonify({"error": "Order not found"}), 404

        return jsonify(response["Item"]), 200

    except Exception as e:
        logger.exception(f"Error retrieving order: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/orders/<order_id>", methods=["PUT"])
@require_auth
def update_order(order_id: str) -> Tuple[Dict[str, Any], int]:
    """Update order status"""
    log_request()

    try:
        data = request.get_json()

        if "status" not in data:
            return jsonify({"error": "Missing status field"}), 400

        # Update item
        orders_table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": data["status"],
                ":updated_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"Order updated: {order_id} -> {data['status']}")
        record_metric("OrderUpdated")

        return (
            jsonify(
                {
                    "order_id": order_id,
                    "status": data["status"],
                    "message": "Order updated successfully",
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception(f"Error updating order: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ===== STATUS ENDPOINTS =====


@app.route("/api/status", methods=["GET"])
def get_status() -> Tuple[Dict[str, Any], int]:
    """Get service status"""
    return (
        jsonify(
            {
                "service": PROJECT_NAME,
                "environment": ENVIRONMENT,
                "status": "running",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0.0",
            }
        ),
        200,
    )


@app.route("/api/metrics", methods=["GET"])
@require_auth
def get_metrics() -> Tuple[Dict[str, Any], int]:
    """Get service metrics"""
    return (
        jsonify(
            {
                "environment": ENVIRONMENT,
                "memory_usage": "N/A",
                "cpu_usage": "N/A",
                "requests_processed": "See CloudWatch",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ),
        200,
    )


# ===== ERROR HANDLERS =====


@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    logger.warning(f"404 Not Found: {request.path}")
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    logger.error(f"500 Internal Server Error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


@app.before_request
def before_request():
    """Before request hook"""
    log_request()


@app.after_request
def after_request(response):
    """After request hook"""
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Log response
    logger.info(f"Response: {response.status_code}")

    return response


# ===== APPLICATION STARTUP =====

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"

    logger.info(f"Starting {PROJECT_NAME} server on port {port}")
    logger.info(f"Environment: {ENVIRONMENT}")

    app.run(host="0.0.0.0", port=port, debug=debug)
