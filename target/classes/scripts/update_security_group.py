import boto3


def update_security_group_inbound_rules(env_name, backend_security_group_name, region):
    # Initialize boto3 clients
    eb = boto3.client('elasticbeanstalk', region_name=region)
    autoscaling = boto3.client('autoscaling', region_name=region)
    ec2 = boto3.client('ec2', region_name=region)

    # Fetch the Auto Scaling group name associated with the Elastic Beanstalk environment
    auto_scaling_group_name = eb.describe_environment_resources(
        EnvironmentName=env_name
    )['EnvironmentResources']['AutoScalingGroups'][0]['Name']
    print(f"AUTO_SCALING_GROUP_NAME: {auto_scaling_group_name}")

    # Fetch the instance ID from the Auto Scaling group
    instance_id = autoscaling.describe_auto_scaling_groups(
        AutoScalingGroupNames=[auto_scaling_group_name]
    )['AutoScalingGroups'][0]['Instances'][0]['InstanceId']
    print(f"INSTANCE_ID: {instance_id}")

    # Fetch the security group ID associated with the instance
    instance_security_group_id = ec2.describe_instances(
        InstanceIds=[instance_id]
    )['Reservations'][0]['Instances'][0]['SecurityGroups'][0]['GroupId']
    print(f"INSTANCE_SECURITY_GROUP_ID: {instance_security_group_id}")

    # Fetch the backend security group ID
    backend_security_group_id = ec2.describe_security_groups(
        Filters=[{'Name': 'group-name', 'Values': [backend_security_group_name]}]
    )['SecurityGroups'][0]['GroupId']
    print(f"BACKEND_SECURITY_GROUP_ID: {backend_security_group_id}")

    # Add inbound rule to allow MySQL (RDS) traffic on port 3306
    ec2.authorize_security_group_ingress(
        GroupId=backend_security_group_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 3306,
            'ToPort': 3306,
            'UserIdGroupPairs': [{'GroupId': instance_security_group_id}]
        }]
    )
    print("Added inbound rule for MySQL (RDS) traffic on port 3306.")

    # Add inbound rule to allow Memcached (ElastiCache) traffic on port 11211
    ec2.authorize_security_group_ingress(
        GroupId=backend_security_group_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 11211,
            'ToPort': 11211,
            'UserIdGroupPairs': [{'GroupId': instance_security_group_id}]
        }]
    )
    print("Added inbound rule for Memcached (ElastiCache) traffic on port 11211.")

    # Add inbound rule to allow RabbitMQ (Amazon MQ) traffic on port 5672
    ec2.authorize_security_group_ingress(
        GroupId=backend_security_group_id,
        IpPermissions=[{
            'IpProtocol': 'tcp',
            'FromPort': 5672,
            'ToPort': 5672,
            'UserIdGroupPairs': [{'GroupId': instance_security_group_id}]
        }]
    )
    print("Added inbound rule for RabbitMQ (Amazon MQ) traffic on port 5672.")

    # Verification
    ip_permissions = ec2.describe_security_groups(
        GroupIds=[backend_security_group_id]
    )['SecurityGroups'][0]['IpPermissions']
    print(f"Updated Inbound Rules: {ip_permissions}")


# Parameters
REGION = "ap-south-1"
ENV_NAME = "dmanup-aws-codecomit-demo-env"
BACKEND_SECURITY_GROUP_NAME = "dmanup-aws-codecomit-backend-secgrp"

# Update security group inbound rules
update_security_group_inbound_rules(ENV_NAME, BACKEND_SECURITY_GROUP_NAME, REGION)
