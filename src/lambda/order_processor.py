"""
Order Processor Lambda Function
Processes incoming orders and triggers workflows
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSEvent
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType
from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError

# Initialize AWS SDK clients
dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")
s3_client = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "my-app")
DYNAMODB_TABLE = f"{PROJECT_NAME}-orders-{ENVIRONMENT}"
SFN_STATE_MACHINE = (
    f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:{PROJECT_NAME}-order-workflow-{ENVIRONMENT}"
)

# DynamoDB table
orders_table = dynamodb.Table(DYNAMODB_TABLE)


class OrderProcessor:
    """Process and validate orders"""

    @staticmethod
    def validate_order(order: Dict[str, Any]) -> bool:
        """Validate order structure and content"""
        required_fields = ["order_id", "customer_id", "items", "amount"]
        return all(field in order for field in required_fields)

    @staticmethod
    def calculate_total(items: list) -> float:
        """Calculate order total from items"""
        return sum(item.get("price", 0) * item.get("quantity", 0) for item in items)

    @staticmethod
    def enrich_order(order: Dict[str, Any]) -> Dict[str, Any]:
        """Add metadata to order"""
        order["timestamp"] = datetime.utcnow().isoformat()
        order["status"] = "received"
        order["total"] = OrderProcessor.calculate_total(order.get("items", []))
        return order


def process_order(sqs_message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process individual order from SQS message

    Args:
        sqs_message: SQS message body containing order data

    Returns:
        Dict containing processing result

    Raises:
        ValueError: If order validation fails
    """
    with tracer.capture_span("process_order"):
        try:
            # Parse the message body
            order = json.loads(sqs_message["body"])
            order_id = order.get("order_id")

            logger.info(f"Processing order: {order_id}")

            # Validate order
            if not OrderProcessor.validate_order(order):
                raise ValueError(f"Invalid order structure: {order_id}")

            # Enrich order with metadata
            order = OrderProcessor.enrich_order(order)

            # Save to DynamoDB
            save_order_to_dynamodb(order)

            # Publish custom metric
            metrics.add_metric(
                name="OrderProcessed",
                unit="Count",
                value=1,
                namespace=f"{PROJECT_NAME}/{ENVIRONMENT}",
            )

            # Trigger Step Functions workflow
            execution_result = trigger_workflow(order)

            logger.info(f"Order {order_id} processed successfully")

            return {
                "statusCode": 200,
                "order_id": order_id,
                "execution_arn": execution_result.get("executionArn"),
                "message": "Order processed successfully",
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise
        except ValueError as e:
            logger.warning(f"Order validation error: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error processing order: {str(e)}")
            metrics.add_metric(
                name="OrderProcessingError",
                unit="Count",
                value=1,
                namespace=f"{PROJECT_NAME}/{ENVIRONMENT}",
            )
            raise


def save_order_to_dynamodb(order: Dict[str, Any]) -> None:
    """
    Save order to DynamoDB

    Args:
        order: Order data to save
    """
    with tracer.capture_span("save_to_dynamodb"):
        try:
            orders_table.put_item(Item=order)
            logger.debug(f"Order saved to DynamoDB: {order.get('order_id')}")
        except Exception as e:
            logger.error(f"Failed to save order to DynamoDB: {str(e)}")
            raise


def trigger_workflow(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trigger Step Functions workflow for order processing

    Args:
        order: Order data

    Returns:
        Step Functions execution response
    """
    with tracer.capture_span("trigger_workflow"):
        try:
            execution_name = f"{order['order_id']}-{datetime.utcnow().timestamp()}"

            response = sfn_client.start_execution(
                stateMachineArn=SFN_STATE_MACHINE, name=execution_name, input=json.dumps(order)
            )

            logger.info(f"Workflow triggered: {response['executionArn']}")
            return response

        except Exception as e:
            logger.error(f"Failed to trigger workflow: {str(e)}")
            raise


def record_metrics() -> None:
    """Record metrics to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace=f"{PROJECT_NAME}/{ENVIRONMENT}",
            MetricData=[
                {
                    "MetricName": "OrderProcessingDuration",
                    "Value": 100,  # milliseconds (example)
                    "Unit": "Milliseconds",
                    "Timestamp": datetime.utcnow(),
                }
            ],
        )
    except Exception as e:
        logger.error(f"Failed to record metrics: {str(e)}")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_cold_start_metric
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing orders from SQS

    Args:
        event: Lambda event (SQS event)
        context: Lambda context

    Returns:
        Response dict with status and results
    """
    sqs_event = SQSEvent(event)
    processor = BatchProcessor(event_type=EventType.SQS)

    # Process messages with batch processor for error handling
    results = processor.process(
        records=sqs_event.records, handler=process_order, errors_as_response=True
    )

    # Log batch processing results
    logger.info(
        f"Batch processing complete. Successful: {len(results['successful'])}, Failed: {len(results['failed'])}"
    )

    # Record metrics
    record_metrics()

    # Emit metrics
    metrics.flush()

    return {
        "statusCode": 200,
        "processed": len(results["successful"]),
        "failed": len(results["failed"]),
        "results": results,
    }


if __name__ == "__main__":
    # Local testing
    test_event = {
        "Records": [
            {
                "messageId": "test-1",
                "body": json.dumps(
                    {
                        "order_id": "ORD-001",
                        "customer_id": "CUST-123",
                        "items": [{"sku": "ITEM-1", "quantity": 2, "price": 29.99}],
                        "amount": 59.98,
                    }
                ),
            }
        ]
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
