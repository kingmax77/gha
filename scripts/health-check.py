#!/usr/bin/env python3
"""
Health Check Script
Verifies that deployed services are functioning correctly
"""

import sys
import time
import logging
import json
from typing import Dict, Tuple
import argparse

import requests
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS clients
ecs_client = boto3.client('ecs')
elb_client = boto3.client('elbv2')
lambda_client = boto3.client('lambda')
sfn_client = boto3.client('stepfunctions')


class HealthChecker:
    """Health check orchestrator"""

    def __init__(self, environment: str, project_name: str = 'my-app'):
        self.environment = environment
        self.project_name = project_name
        self.results = {}
        self.all_healthy = True

    def check_ecs_service(self, cluster_name: str, service_name: str) -> bool:
        """Check ECS service health"""
        logger.info(f"Checking ECS service: {service_name}")
        
        try:
            # Describe service
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            if not response['services']:
                logger.error(f"Service not found: {service_name}")
                self.results['ecs_service'] = False
                return False
            
            service = response['services'][0]
            
            # Check service status
            if service['status'] != 'ACTIVE':
                logger.error(f"Service not active: {service['status']}")
                self.results['ecs_service'] = False
                return False
            
            # Check desired vs running tasks
            desired = service['desiredCount']
            running = service['runningCount']
            
            if running < desired:
                logger.warning(f"Running tasks ({running}) < Desired ({desired})")
                # Allow some time for tasks to start
                time.sleep(10)
                response = ecs_client.describe_services(
                    cluster=cluster_name,
                    services=[service_name]
                )
                service = response['services'][0]
                running = service['runningCount']
            
            if running < desired:
                logger.error(f"Not enough running tasks: {running}/{desired}")
                self.results['ecs_service'] = False
                return False
            
            # List tasks
            tasks_response = ecs_client.list_tasks(
                cluster=cluster_name,
                serviceName=service_name,
                desiredStatus='RUNNING'
            )
            
            if len(tasks_response['taskArns']) < desired:
                logger.error(f"Not enough running task ARNs")
                self.results['ecs_service'] = False
                return False
            
            # Describe tasks for more details
            tasks = ecs_client.describe_tasks(
                cluster=cluster_name,
                tasks=tasks_response['taskArns']
            )
            
            for task in tasks['tasks']:
                if task['lastStatus'] != 'RUNNING':
                    logger.warning(f"Task not running: {task['taskArn']}")
                
                # Check health
                if 'containers' in task:
                    for container in task['containers']:
                        if container.get('lastStatus') != 'RUNNING':
                            logger.error(f"Container not running: {container['name']}")
                            self.results['ecs_service'] = False
                            return False
            
            logger.info(f"✓ ECS service healthy: {running} running tasks")
            self.results['ecs_service'] = True
            return True
        
        except ClientError as e:
            logger.error(f"ECS check failed: {e}")
            self.results['ecs_service'] = False
            return False

    def check_alb_targets(self, target_group_arn: str) -> bool:
        """Check ALB target health"""
        logger.info("Checking ALB targets")
        
        try:
            response = elb_client.describe_target_health(
                TargetGroupArn=target_group_arn
            )
            
            targets = response.get('TargetHealthDescriptions', [])
            
            if not targets:
                logger.error("No targets found in ALB")
                self.results['alb_targets'] = False
                return False
            
            healthy_count = sum(
                1 for t in targets
                if t['TargetHealth']['State'] == 'healthy'
            )
            
            logger.info(f"ALB targets: {healthy_count}/{len(targets)} healthy")
            
            if healthy_count > 0:
                self.results['alb_targets'] = True
                return True
            else:
                self.results['alb_targets'] = False
                return False
        
        except ClientError as e:
            logger.error(f"ALB check failed: {e}")
            self.results['alb_targets'] = False
            return False

    def check_endpoint(self, url: str, timeout: int = 5) -> bool:
        """Check HTTP endpoint"""
        logger.info(f"Checking endpoint: {url}")
        
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={'X-API-Key': 'health-check'}
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Endpoint healthy: {response.status_code}")
                self.results['endpoint'] = True
                return True
            elif response.status_code in [503, 503]:
                # Service might be starting up
                logger.warning(f"Endpoint degraded: {response.status_code}")
                self.results['endpoint'] = 'degraded'
                return True
            else:
                logger.error(f"Endpoint unhealthy: {response.status_code}")
                self.results['endpoint'] = False
                return False
        
        except requests.RequestException as e:
            logger.error(f"Endpoint check failed: {e}")
            self.results['endpoint'] = False
            return False

    def check_lambda_function(self, function_name: str) -> bool:
        """Check Lambda function"""
        logger.info(f"Checking Lambda function: {function_name}")
        
        try:
            response = lambda_client.get_function(
                FunctionName=function_name
            )
            
            state = response['Configuration']['State']
            
            if state != 'Active':
                logger.error(f"Lambda function not active: {state}")
                self.results['lambda'] = False
                return False
            
            logger.info(f"✓ Lambda function active")
            self.results['lambda'] = True
            return True
        
        except ClientError as e:
            logger.error(f"Lambda check failed: {e}")
            self.results['lambda'] = False
            return False

    def check_step_functions(self, state_machine_arn: str) -> bool:
        """Check Step Functions state machine"""
        logger.info("Checking Step Functions")
        
        try:
            response = sfn_client.describe_state_machine(
                stateMachineArn=state_machine_arn
            )
            
            status = response['status']
            
            if status != 'ACTIVE':
                logger.error(f"State machine not active: {status}")
                self.results['step_functions'] = False
                return False
            
            logger.info(f"✓ Step Functions state machine active")
            self.results['step_functions'] = True
            return True
        
        except ClientError as e:
            logger.error(f"Step Functions check failed: {e}")
            self.results['step_functions'] = False
            return False

    def run_all_checks(self,
                      cluster_name: str = None,
                      service_name: str = None,
                      target_group_arn: str = None,
                      endpoint_url: str = None,
                      lambda_functions: list = None,
                      state_machine_arn: str = None) -> bool:
        """Run all health checks"""
        logger.info(f"Starting health checks for {self.environment}")
        
        checks_passed = 0
        checks_total = 0
        
        # ECS Service Check
        if cluster_name and service_name:
            checks_total += 1
            if self.check_ecs_service(cluster_name, service_name):
                checks_passed += 1
        
        # ALB Targets Check
        if target_group_arn:
            checks_total += 1
            if self.check_alb_targets(target_group_arn):
                checks_passed += 1
        
        # Endpoint Check
        if endpoint_url:
            checks_total += 1
            for _ in range(3):  # Retry up to 3 times
                if self.check_endpoint(endpoint_url):
                    checks_passed += 1
                    break
                time.sleep(5)
        
        # Lambda Function Checks
        if lambda_functions:
            for func_name in lambda_functions:
                checks_total += 1
                if self.check_lambda_function(func_name):
                    checks_passed += 1
        
        # Step Functions Check
        if state_machine_arn:
            checks_total += 1
            if self.check_step_functions(state_machine_arn):
                checks_passed += 1
        
        # Summary
        logger.info(f"\n{'='*50}")
        logger.info(f"Health Check Summary")
        logger.info(f"{'='*50}")
        logger.info(f"Passed: {checks_passed}/{checks_total}")
        logger.info(f"Results: {json.dumps(self.results, indent=2)}")
        logger.info(f"{'='*50}\n")
        
        return checks_passed == checks_total


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Health check for deployed services')
    parser.add_argument('environment', choices=['dev', 'staging', 'prod'],
                       help='Deployment environment')
    parser.add_argument('--cluster', help='ECS cluster name')
    parser.add_argument('--service', help='ECS service name')
    parser.add_argument('--target-group', help='ALB target group ARN')
    parser.add_argument('--endpoint', help='Service endpoint URL')
    parser.add_argument('--lambda-functions', nargs='+', help='Lambda function names')
    parser.add_argument('--state-machine', help='Step Functions state machine ARN')
    parser.add_argument('--timeout', type=int, default=300,
                       help='Timeout in seconds')
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.environment)
    
    start_time = time.time()
    
    # Run checks with timeout
    while time.time() - start_time < args.timeout:
        all_healthy = checker.run_all_checks(
            cluster_name=args.cluster,
            service_name=args.service,
            target_group_arn=args.target_group,
            endpoint_url=args.endpoint,
            lambda_functions=args.lambda_functions,
            state_machine_arn=args.state_machine
        )
        
        if all_healthy:
            logger.info("✓ All health checks passed!")
            return 0
        
        elapsed = time.time() - start_time
        remaining = args.timeout - elapsed
        
        if remaining > 0:
            logger.info(f"Retrying in 10 seconds... ({remaining:.0f}s remaining)")
            time.sleep(10)
        else:
            break
    
    logger.error("✗ Health checks failed!")
    return 1


if __name__ == '__main__':
    sys.exit(main())
