"""
Data Transformer Lambda Function
Transforms and enriches order data for analytics and reporting
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List
import hashlib

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from botocore.exceptions import ClientError

# Initialize AWS SDK clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "my-app")
BUCKET_NAME = f"{PROJECT_NAME}-data-{ENVIRONMENT}"
ANALYTICS_TABLE = f"{PROJECT_NAME}-analytics-{ENVIRONMENT}"

# DynamoDB table
analytics_table = dynamodb.Table(ANALYTICS_TABLE)


class DataTransformer:
    """Transform and enrich data"""

    @staticmethod
    def calculate_metrics(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate metrics from order items"""
        total_quantity = sum(item.get("quantity", 0) for item in items)
        total_value = sum(item.get("price", 0) * item.get("quantity", 0) for item in items)
        average_price = total_value / total_quantity if total_quantity > 0 else 0

        return {
            "total_quantity": total_quantity,
            "total_value": total_value,
            "average_price": round(average_price, 2),
            "item_count": len(items),
        }

    @staticmethod
    def enrich_order_data(order: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich order with calculated metrics"""
        enriched_order = order.copy()

        # Add calculated metrics
        items_metrics = DataTransformer.calculate_metrics(order.get("items", []))
        enriched_order.update(items_metrics)

        # Add hash for deduplication
        order_hash = hashlib.sha256(json.dumps(order, sort_keys=True).encode()).hexdigest()
        enriched_order["order_hash"] = order_hash

        # Add transformation metadata
        enriched_order["transformed_at"] = datetime.utcnow().isoformat()
        enriched_order["transformation_version"] = "1.0"

        # Add categorization
        enriched_order["order_size"] = DataTransformer.categorize_order_size(
            items_metrics["total_value"]
        )
        enriched_order["priority"] = DataTransformer.calculate_priority(
            items_metrics["total_value"], order.get("customer_status", "standard")
        )

        return enriched_order

    @staticmethod
    def categorize_order_size(total_value: float) -> str:
        """Categorize order by size"""
        if total_value < 50:
            return "small"
        elif total_value < 200:
            return "medium"
        elif total_value < 500:
            return "large"
        else:
            return "enterprise"

    @staticmethod
    def calculate_priority(total_value: float, customer_status: str) -> str:
        """Calculate order priority"""
        base_priority = 3  # Medium

        if total_value > 500:
            base_priority = 1  # High
        elif total_value > 200:
            base_priority = 2  # Medium-High
        elif total_value < 50:
            base_priority = 4  # Low

        # Adjust for customer status
        if customer_status == "premium":
            base_priority = max(1, base_priority - 1)
        elif customer_status == "vip":
            base_priority = 1

        return ["critical", "high", "medium", "low", "very_low"][base_priority - 1]


def transform_order_data(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform order data

    Args:
        order: Raw order data

    Returns:
        Transformed and enriched order
    """
    with tracer.capture_span("transform_data"):
        try:
            logger.info(f"Transforming order: {order.get('order_id')}")

            # Validate required fields
            if not order.get("order_id"):
                raise ValueError("Missing order_id")

            # Transform data
            transformed = DataTransformer.enrich_order_data(order)

            # Validate transformed data
            if not validate_transformed_data(transformed):
                raise ValueError("Validation failed on transformed data")

            logger.debug(f"Order transformed successfully: {order.get('order_id')}")
            metrics.add_metric("DataTransformed", 1, "Count")

            return transformed

        except Exception as e:
            logger.error(f"Data transformation error: {str(e)}")
            metrics.add_metric("TransformationError", 1, "Count")
            raise


def validate_transformed_data(data: Dict[str, Any]) -> bool:
    """
    Validate transformed data

    Args:
        data: Transformed data to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "order_id",
        "total_quantity",
        "total_value",
        "order_hash",
        "order_size",
        "priority",
    ]

    return all(field in data for field in required_fields)


def save_to_analytics(order: Dict[str, Any]) -> None:
    """
    Save transformed data to analytics table

    Args:
        order: Transformed order data
    """
    with tracer.capture_span("save_analytics"):
        try:
            # Create analytics record
            analytics_record = {
                "order_id": order.get("order_id"),
                "timestamp": datetime.utcnow().isoformat(),
                "date": datetime.utcnow().date().isoformat(),
                "customer_id": order.get("customer_id"),
                "total_value": order.get("total_value"),
                "total_quantity": order.get("total_quantity"),
                "average_price": order.get("average_price"),
                "order_size": order.get("order_size"),
                "priority": order.get("priority"),
                "item_count": order.get("item_count"),
                "status": order.get("status", "unknown"),
                "environment": ENVIRONMENT,
                "order_hash": order.get("order_hash"),
            }

            # Save to DynamoDB
            analytics_table.put_item(Item=analytics_record)
            logger.debug(f"Analytics record saved: {order.get('order_id')}")

        except ClientError as e:
            logger.error(f"Failed to save analytics record: {str(e)}")
            metrics.add_metric("AnalyticsSaveError", 1, "Count")
            raise


def save_to_s3_parquet(order: Dict[str, Any]) -> str:
    """
    Save transformed data to S3 for batch processing

    Args:
        order: Transformed order data

    Returns:
        S3 object key
    """
    with tracer.capture_span("save_s3"):
        try:
            # Create S3 key with date partition
            date_partition = datetime.utcnow().date().isoformat()
            s3_key = f"orders/transformed/{date_partition}/{order['order_id']}.json"

            # Upload to S3
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(order),
                ContentType="application/json",
                Metadata={
                    "order_id": order.get("order_id"),
                    "transformed_at": order.get("transformed_at"),
                    "order_hash": order.get("order_hash"),
                },
            )

            logger.debug(f"Order saved to S3: {s3_key}")
            metrics.add_metric("S3ObjectCreated", 1, "Count")

            return s3_key

        except ClientError as e:
            logger.error(f"Failed to save to S3: {str(e)}")
            metrics.add_metric("S3SaveError", 1, "Count")
            raise


def generate_statistics(transformed_orders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate statistics from transformed orders

    Args:
        transformed_orders: List of transformed orders

    Returns:
        Statistics dictionary
    """
    with tracer.capture_span("generate_stats"):
        if not transformed_orders:
            return {}

        total_value = sum(o.get("total_value", 0) for o in transformed_orders)
        total_items = sum(o.get("total_quantity", 0) for o in transformed_orders)
        average_order_value = total_value / len(transformed_orders)

        # Count by size
        size_counts = {}
        for order in transformed_orders:
            size = order.get("order_size", "unknown")
            size_counts[size] = size_counts.get(size, 0) + 1

        # Count by priority
        priority_counts = {}
        for order in transformed_orders:
            priority = order.get("priority", "unknown")
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        return {
            "total_orders": len(transformed_orders),
            "total_value": round(total_value, 2),
            "total_items": total_items,
            "average_order_value": round(average_order_value, 2),
            "size_distribution": size_counts,
            "priority_distribution": priority_counts,
        }


def publish_metrics(stats: Dict[str, Any]) -> None:
    """
    Publish statistics to CloudWatch

    Args:
        stats: Statistics dictionary
    """
    with tracer.capture_span("publish_metrics"):
        try:
            metric_data = [
                {
                    "MetricName": "TotalOrderValue",
                    "Value": stats.get("total_value", 0),
                    "Unit": "None",
                },
                {
                    "MetricName": "AverageOrderValue",
                    "Value": stats.get("average_order_value", 0),
                    "Unit": "None",
                },
                {"MetricName": "TotalItems", "Value": stats.get("total_items", 0), "Unit": "Count"},
            ]

            cloudwatch.put_metric_data(
                Namespace=f"{PROJECT_NAME}/{ENVIRONMENT}", MetricData=metric_data
            )

            logger.debug("Metrics published to CloudWatch")

        except ClientError as e:
            logger.error(f"Failed to publish metrics: {str(e)}")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_cold_start_metric
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for data transformation

    Args:
        event: Lambda event containing order data
        context: Lambda context

    Returns:
        Response dict with transformation results
    """
    try:
        # Extract order from event
        order = event.get("order") or event

        if not order:
            raise ValueError("No order data provided")

        logger.info(f"Processing transformation for order: {order.get('order_id')}")

        # Transform the order
        transformed_order = transform_order_data(order)

        # Save to analytics
        save_to_analytics(transformed_order)

        # Save to S3
        s3_key = save_to_s3_parquet(transformed_order)

        # Generate and publish statistics
        stats = generate_statistics([transformed_order])
        publish_metrics(stats)

        metrics.flush()

        return {
            "statusCode": 200,
            "order_id": transformed_order.get("order_id"),
            "s3_key": s3_key,
            "transformed_data": transformed_order,
            "statistics": stats,
            "message": "Data transformation completed successfully",
        }

    except Exception as e:
        logger.exception(f"Lambda handler error: {str(e)}")
        metrics.add_metric("LambdaError", 1, "Count")
        metrics.flush()
        raise


if __name__ == "__main__":
    # Local testing
    test_event = {
        "order_id": "ORD-001",
        "customer_id": "CUST-123",
        "customer_status": "premium",
        "items": [
            {"sku": "ITEM-1", "quantity": 2, "price": 29.99},
            {"sku": "ITEM-2", "quantity": 1, "price": 49.99},
        ],
        "status": "confirmed",
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2, default=str))
