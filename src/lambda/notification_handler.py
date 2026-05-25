"""
Notification Handler Lambda Function
Sends notifications based on order events
"""

import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from botocore.exceptions import ClientError

# Initialize AWS SDK clients
ses_client = boto3.client("ses")
sns_client = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")

# Initialize Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "my-app")
NOTIFICATION_TABLE = f"{PROJECT_NAME}-notifications-{ENVIRONMENT}"
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@example.com")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

# DynamoDB table
notifications_table = dynamodb.Table(NOTIFICATION_TABLE)


class NotificationType(str, Enum):
    """Notification types"""

    ORDER_CONFIRMED = "order_confirmed"
    ORDER_SHIPPED = "order_shipped"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FAILED = "order_failed"


class NotificationChannel(str, Enum):
    """Notification channels"""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    SNS = "sns"


class NotificationHandler:
    """Handle sending notifications"""

    @staticmethod
    def format_order_confirmed(order: Dict[str, Any]) -> Dict[str, str]:
        """Format order confirmed notification"""
        return {
            "subject": f"Order Confirmed - {order.get('order_id')}",
            "html_body": f"""
                <html>
                    <body>
                        <h2>Order Confirmed</h2>
                        <p>Your order has been confirmed.</p>
                        <p><strong>Order ID:</strong> {order.get('order_id')}</p>
                        <p><strong>Total Amount:</strong> ${order.get('total', 0):.2f}</p>
                        <p><strong>Status:</strong> {order.get('status', 'Unknown')}</p>
                        <p>Thank you for your order!</p>
                    </body>
                </html>
            """,
            "text_body": f"Order confirmed: {order.get('order_id')} - Total: ${order.get('total', 0):.2f}",
        }

    @staticmethod
    def format_order_shipped(order: Dict[str, Any]) -> Dict[str, str]:
        """Format order shipped notification"""
        return {
            "subject": f"Order Shipped - {order.get('order_id')}",
            "html_body": f"""
                <html>
                    <body>
                        <h2>Order Shipped</h2>
                        <p>Your order has been shipped.</p>
                        <p><strong>Order ID:</strong> {order.get('order_id')}</p>
                        <p><strong>Tracking Number:</strong> {order.get('tracking_number', 'N/A')}</p>
                        <p>Track your order using the tracking number above.</p>
                    </body>
                </html>
            """,
            "text_body": f"Order shipped: {order.get('order_id')} - Tracking: {order.get('tracking_number', 'N/A')}",
        }

    @staticmethod
    def format_order_failed(order: Dict[str, Any], error: str) -> Dict[str, str]:
        """Format order failed notification"""
        return {
            "subject": f"Order Processing Failed - {order.get('order_id')}",
            "html_body": f"""
                <html>
                    <body>
                        <h2>Order Processing Failed</h2>
                        <p>Unfortunately, there was an issue processing your order.</p>
                        <p><strong>Order ID:</strong> {order.get('order_id')}</p>
                        <p><strong>Error:</strong> {error}</p>
                        <p>Please contact support for assistance.</p>
                    </body>
                </html>
            """,
            "text_body": f"Order processing failed: {order.get('order_id')} - Error: {error}",
        }


def send_email(recipient: str, subject: str, html_body: str, text_body: str) -> Dict[str, Any]:
    """
    Send email notification using SES

    Args:
        recipient: Email address
        subject: Email subject
        html_body: HTML email body
        text_body: Plain text email body

    Returns:
        SES response
    """
    with tracer.capture_span("send_email"):
        try:
            response = ses_client.send_email(
                Source=FROM_EMAIL,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Html": {"Data": html_body}, "Text": {"Data": text_body}},
                },
            )
            logger.info(f"Email sent successfully. MessageId: {response['MessageId']}")
            metrics.add_metric("EmailSent", 1, "Count")
            return response

        except ClientError as e:
            logger.error(f"Failed to send email: {e.response['Error']['Message']}")
            metrics.add_metric("EmailSendFailed", 1, "Count")
            raise


def send_sns_notification(message: str, subject: str = None) -> Dict[str, Any]:
    """
    Send SNS notification

    Args:
        message: Message content
        subject: Message subject

    Returns:
        SNS response
    """
    with tracer.capture_span("send_sns"):
        try:
            response = sns_client.publish(
                TopicArn=SNS_TOPIC_ARN, Message=message, Subject=subject or "Notification"
            )
            logger.info(f"SNS notification sent. MessageId: {response['MessageId']}")
            metrics.add_metric("SNSNotificationSent", 1, "Count")
            return response

        except ClientError as e:
            logger.error(f"Failed to send SNS notification: {e.response['Error']['Message']}")
            metrics.add_metric("SNSNotificationFailed", 1, "Count")
            raise


def save_notification_record(
    order_id: str,
    notification_type: NotificationType,
    channel: NotificationChannel,
    recipient: str,
    status: str,
) -> None:
    """
    Save notification record to DynamoDB

    Args:
        order_id: Order ID
        notification_type: Type of notification
        channel: Notification channel used
        recipient: Recipient address
        status: Notification status
    """
    with tracer.capture_span("save_notification"):
        try:
            notifications_table.put_item(
                Item={
                    "notification_id": f"{order_id}#{datetime.utcnow().isoformat()}",
                    "order_id": order_id,
                    "type": notification_type.value,
                    "channel": channel.value,
                    "recipient": recipient,
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    "environment": ENVIRONMENT,
                }
            )
            logger.debug(f"Notification record saved for order: {order_id}")

        except ClientError as e:
            logger.error(f"Failed to save notification record: {str(e)}")
            raise


def process_notification(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process notification event from Step Functions

    Args:
        event: Event data containing order and notification details

    Returns:
        Processing result
    """
    order_id = event.get("order_id")
    notification_type = event.get("notification_type", "order_confirmed")
    customer_email = event.get("customer_email")
    customer_phone = event.get("customer_phone")

    logger.info(f"Processing notification for order: {order_id}, type: {notification_type}")

    try:
        # Format notification based on type
        notification_type_enum = NotificationType(notification_type)

        if notification_type_enum == NotificationType.ORDER_CONFIRMED:
            notification_content = NotificationHandler.format_order_confirmed(event)
        elif notification_type_enum == NotificationType.ORDER_SHIPPED:
            notification_content = NotificationHandler.format_order_shipped(event)
        elif notification_type_enum == NotificationType.ORDER_FAILED:
            notification_content = NotificationHandler.format_order_failed(
                event, event.get("error", "Unknown error")
            )
        else:
            notification_content = {
                "subject": f"Order Notification - {order_id}",
                "html_body": json.dumps(event),
                "text_body": json.dumps(event),
            }

        # Send email notification
        if customer_email:
            send_email(
                recipient=customer_email,
                subject=notification_content["subject"],
                html_body=notification_content["html_body"],
                text_body=notification_content["text_body"],
            )
            save_notification_record(
                order_id, notification_type_enum, NotificationChannel.EMAIL, customer_email, "sent"
            )

        # Send SNS notification for critical events
        if notification_type_enum in [NotificationType.ORDER_FAILED]:
            send_sns_notification(
                message=notification_content["text_body"], subject=notification_content["subject"]
            )

        metrics.add_metric("NotificationProcessed", 1, "Count")

        return {
            "statusCode": 200,
            "order_id": order_id,
            "notification_type": notification_type,
            "message": "Notification sent successfully",
        }

    except Exception as e:
        logger.exception(f"Failed to process notification: {str(e)}")
        metrics.add_metric("NotificationProcessingError", 1, "Count")
        raise


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_cold_start_metric
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for notification processing

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        Response dict with status
    """
    try:
        result = process_notification(event)
        metrics.flush()
        return result

    except Exception as e:
        logger.exception(f"Lambda handler error: {str(e)}")
        metrics.add_metric("LambdaError", 1, "Count")
        metrics.flush()
        raise


if __name__ == "__main__":
    # Local testing
    test_event = {
        "order_id": "ORD-001",
        "customer_email": "customer@example.com",
        "customer_phone": "+1234567890",
        "notification_type": "order_confirmed",
        "total": 99.99,
        "status": "confirmed",
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
