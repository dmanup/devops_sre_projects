import boto3
import json
import time
import requests


def get_or_create_secret(secret_name, region):
    client = boto3.client('secretsmanager', region_name=region)

    try:
        # Check if the secret already exists
        response = client.describe_secret(SecretId=secret_name)
        # Fetch the secret value
        secret_response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(secret_response['SecretString'])
        print(f"Secret {secret_name} already exists.")
    except client.exceptions.ResourceNotFoundException:
        # Generate a secure password
        import secrets
        password = ''.join(secrets.choice(
            'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&()*+,-./:;<=>?@[]^_`{|}~') for i in
                           range(16))
        secret = {
            "username": "admin",
            "password": password
        }
        # Store the secret in AWS Secrets Manager
        client.create_secret(
            Name=secret_name,
            Description="MQ broker credentials",
            SecretString=json.dumps(secret)
        )
        print(f"Stored new secret {secret_name} in AWS Secrets Manager.")

    return secret


def create_or_get_mq_broker(broker_name, broker_instance_type, engine_version, subnet_id, security_group_id, region):
    mq = boto3.client('mq', region_name=region)

    # Check if the broker already exists
    try:
        response = mq.describe_broker(BrokerId=broker_name)
        broker_id = response['BrokerId']
        print(f"MQ Broker {broker_name} already exists with ID: {broker_id}")
        return broker_id
    except mq.exceptions.NotFoundException:
        print(f"MQ Broker {broker_name} does not exist, creating a new one.")

    secret = get_or_create_secret('RabbitMQ_Credentials', region)
    username = secret['username']
    password = secret['password']

    broker_params = {
        'BrokerName': broker_name,
        'DeploymentMode': 'SINGLE_INSTANCE',
        'EngineType': 'RabbitMQ',
        'EngineVersion': engine_version,
        'HostInstanceType': broker_instance_type,
        'SubnetIds': [subnet_id],
        'SecurityGroups': [security_group_id],
        'Users': [{"Username": username, "Password": password}],
        'PubliclyAccessible': False
    }

    #print("Broker parameters:")
    #print(json.dumps(broker_params, indent=2))

    broker_response = mq.create_broker(**broker_params)

    broker_id = broker_response['BrokerId']
    print(f"Creating MQ Broker {broker_name} with ID: {broker_id}")

    while True:
        status = mq.describe_broker(BrokerId=broker_id)['BrokerState']
        print(f"Current Broker Status: {status}")
        if status == 'RUNNING':
            break
        time.sleep(30)

    print(f"MQ Broker {broker_name} is now RUNNING with ID: {broker_id}")
    return broker_id


region = 'ap-south-1'
broker_name = 'dmanup-aws-codecomit-demo-mq-broker'
broker_instance_type = 'mq.t3.micro'
engine_version = '3.8.22'
security_group_name = 'dmanup-aws-codecomit-backend-secgrp'

# Fetch the security group ID
ec2 = boto3.client('ec2', region_name=region)
security_group = ec2.describe_security_groups(Filters=[{'Name': 'group-name', 'Values': [security_group_name]}])
if security_group['SecurityGroups']:
    security_group_id = security_group['SecurityGroups'][0]['GroupId']
    print(f"Security Group ID: {security_group_id}")
else:
    raise Exception(f"Security group '{security_group_name}' not found")

# Fetch VPC ID
vpc_id = ec2.describe_vpcs()['Vpcs'][0]['VpcId']
print(f"VPC ID: {vpc_id}")

# Fetch Subnet IDs
subnet_ids = [subnet['SubnetId'] for subnet in
              ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']]
print(f"Subnet IDs: {subnet_ids}")

# Select a single subnet for SINGLE_INSTANCE deployment mode
subnet_id = subnet_ids[0]

# Create or get the MQ broker
create_or_get_mq_broker(broker_name, broker_instance_type, engine_version, subnet_id, security_group_id, region)
