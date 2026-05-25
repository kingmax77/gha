# ===== CLOUDWATCH DASHBOARDS =====

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # ECS Service Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.app.name, "ClusterName", aws_ecs_cluster.main.name],
            [".", "MemoryUtilization", ".", ".", ".", "."],
            [".", "DesiredTaskCount", ".", ".", ".", "."],
            [".", "RunningCount", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Service Metrics"
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },

      # ALB Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.main.arn_suffix],
            [".", "RequestCount", ".", "."],
            [".", "HealthyHostCount", "TargetGroup", aws_lb_target_group.app.arn_suffix, "LoadBalancer", aws_lb.main.arn_suffix],
            [".", "UnHealthyHostCount", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Load Balancer Metrics"
        }
      },

      # Lambda Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.order_processor.function_name],
            [".", "Duration", ".", "."],
            [".", "Errors", ".", "."],
            [".", "Throttles", ".", "."],
            [".", "ConcurrentExecutions", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Lambda Metrics"
        }
      },

      # Step Functions Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", aws_sfn_state_machine.order_workflow.arn],
            [".", "ExecutionsFailed", ".", "."],
            [".", "ExecutionTime", ".", "."],
            [".", "ExecutionsTimedOut", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Step Functions Metrics"
        }
      },

      # SQS Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.orders.name],
            [".", "NumberOfMessagesSent", ".", "."],
            [".", "NumberOfMessagesReceived", ".", "."],
            [".", "ApproximateAgeOfOldestMessage", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "SQS Queue Metrics"
        }
      },

      # CloudWatch Logs Insights Query
      {
        type = "log"
        properties = {
          query   = "fields @timestamp, @message | stats count() by @message | limit 20"
          region  = var.aws_region
          title   = "Recent Errors"
        }
      }
    ]
  })
}

# ===== CLOUDWATCH ALARMS =====

# ECS CPU High Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "${var.project_name}-ecs-cpu-high-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alert when ECS CPU exceeds 80%"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.errors.arn] : []

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.app.name
  }
}

# ECS Memory High Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  alarm_name          = "${var.project_name}-ecs-memory-high-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "Alert when ECS memory exceeds 85%"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.errors.arn] : []

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.app.name
  }
}

# ECS Task Failures Alarm
resource "aws_cloudwatch_metric_alarm" "ecs_task_failures" {
  alarm_name          = "${var.project_name}-ecs-task-failures-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "RunningCount"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = var.ecs_desired_count - 1
  alarm_description   = "Alert when running tasks drop below desired"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.environment == "prod" ? [aws_sns_topic.errors.arn] : []

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.app.name
  }
}

# Lambda Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when Lambda errors exceed threshold"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    FunctionName = aws_lambda_function.order_processor.function_name
  }
}

# Lambda Throttles Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.project_name}-lambda-throttles-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert when Lambda function is throttled"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    FunctionName = aws_lambda_function.order_processor.function_name
  }
}

# Lambda Duration Alarm
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.project_name}-lambda-duration-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 30000  # 30 seconds in ms
  alarm_description   = "Alert when Lambda execution time exceeds 30s"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    FunctionName = aws_lambda_function.order_processor.function_name
  }
}

# Step Functions Failed Executions Alarm
resource "aws_cloudwatch_metric_alarm" "step_functions_failed" {
  alarm_name          = "${var.project_name}-sfn-failed-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Step Functions executions fail"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.order_workflow.arn
  }
}

# SQS Queue Depth Alarm
resource "aws_cloudwatch_metric_alarm" "sqs_queue_depth" {
  alarm_name          = "${var.project_name}-sqs-depth-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 1000
  alarm_description   = "Alert when SQS queue is backing up"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    QueueName = aws_sqs_queue.orders.name
  }
}

# ALB Unhealthy Targets Alarm
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_targets" {
  alarm_name          = "${var.project_name}-alb-unhealthy-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "Alert when ALB has unhealthy targets"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
    TargetGroup  = aws_lb_target_group.app.arn_suffix
  }
}

# ALB Target Response Time Alarm
resource "aws_cloudwatch_metric_alarm" "alb_response_time" {
  alarm_name          = "${var.project_name}-alb-response-time-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 1.0  # 1 second
  alarm_description   = "Alert when response time exceeds 1 second"
  alarm_actions       = [aws_sns_topic.errors.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }
}

# ===== COMPOSITE ALARM =====
resource "aws_cloudwatch_composite_alarm" "application_health" {
  count = var.environment == "prod" ? 1 : 0

  alarm_name          = "${var.project_name}-application-health-${var.environment}"
  alarm_description   = "Composite alarm for overall application health"
  actions_enabled     = true
  alarm_actions       = [aws_sns_topic.errors.arn]

  alarm_rule = join(" OR ", [
    "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${aws_cloudwatch_metric_alarm.ecs_cpu_high.alarm_name}",
    "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${aws_cloudwatch_metric_alarm.ecs_memory_high.alarm_name}",
    "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${aws_cloudwatch_metric_alarm.lambda_errors.alarm_name}",
    "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${aws_cloudwatch_metric_alarm.step_functions_failed.alarm_name}",
    "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${aws_cloudwatch_metric_alarm.alb_unhealthy_targets.alarm_name}"
  ])
}

# ===== METRIC FILTERS FOR CUSTOM METRICS =====

resource "aws_cloudwatch_log_group_metric_filter" "error_count" {
  name           = "${var.project_name}-error-count-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  filter_pattern = "[time, request_id, level = ERROR, ...]"

  metric_transformation {
    name      = "ErrorCount"
    namespace = "${var.project_name}/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_group_metric_filter" "warning_count" {
  name           = "${var.project_name}-warning-count-${var.environment}"
  log_group_name = aws_cloudwatch_log_group.ecs.name
  filter_pattern = "[time, request_id, level = WARNING, ...]"

  metric_transformation {
    name      = "WarningCount"
    namespace = "${var.project_name}/${var.environment}"
    value     = "1"
  }
}

# ===== OUTPUTS =====
output "dashboard_url" {
  description = "URL to the CloudWatch dashboard"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}
