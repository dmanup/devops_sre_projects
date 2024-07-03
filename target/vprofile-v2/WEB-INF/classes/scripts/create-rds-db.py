# Author: Anup Deshpande
# Date: 01-July-2024
# Script to create & setup the AWS RDS DB with MySQL
# All the components are validated first for their existence
# Components are created only if they are not present.
# Script ensures duplicate components are not created even if script is rerun multiple times.
# Parameters Group & Subnet Group for RDS DB are created.
# Once DB is fully up & available, local Client IP is added into the Security Grp of RDS DB.
# RDS DB Public access is temporarily disabled & tables are created by connecting to DB using mysql client
# Post the successful tables creation, public access & inbound access to IP address is removed

import boto3
import pymysql
import json
import time
import os
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
            Description="RDS MySQL DB credentials",
            SecretString=json.dumps(secret)
        )
        print(f"Stored new secret {secret_name} in AWS Secrets Manager.")

    return secret


def create_or_get_rds_instance(db_instance_identifier, db_instance_class, engine, master_username, master_user_password,
                               db_name, subnet_group_name, security_group_id, parameter_group_name, region):
    rds = boto3.client('rds', region_name=region)

    # Check if the RDS instance already exists
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
        endpoint = response['DBInstances'][0]['Endpoint']['Address']
        print(f"RDS Instance {db_instance_identifier} already exists with endpoint: {endpoint}")
        return endpoint
    except rds.exceptions.DBInstanceNotFoundFault:
        print(f"RDS Instance {db_instance_identifier} does not exist, creating a new one.")

    response = rds.create_db_instance(
        DBInstanceIdentifier=db_instance_identifier,
        DBInstanceClass=db_instance_class,
        Engine=engine,
        MasterUsername=master_username,
        MasterUserPassword=master_user_password,
        AllocatedStorage=20,
        DBSubnetGroupName=subnet_group_name,
        VpcSecurityGroupIds=[security_group_id],
        DBParameterGroupName=parameter_group_name,
        BackupRetentionPeriod=0,
        PubliclyAccessible=True,  # Ensure the RDS instance is publicly accessible
        Port=3306,
        DBName=db_name,
        EngineVersion='8.0',
        StorageType='gp2'
    )

    rds.get_waiter('db_instance_available').wait(DBInstanceIdentifier=db_instance_identifier)
    endpoint = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)['DBInstances'][0]['Endpoint'][
        'Address']
    print(f"Created RDS Endpoint: {endpoint}")
    return endpoint


def modify_public_access(db_instance_identifier, public_access, region):
    rds = boto3.client('rds', region_name=region)
    response = rds.modify_db_instance(
        DBInstanceIdentifier=db_instance_identifier,
        PubliclyAccessible=public_access,
        ApplyImmediately=True
    )
    rds.get_waiter('db_instance_available').wait(DBInstanceIdentifier=db_instance_identifier)
    print(f"Set PubliclyAccessible to {public_access} for RDS instance {db_instance_identifier}")


def create_subnet_group(subnet_group_name, subnet_ids, region):
    rds = boto3.client('rds', region_name=region)
    try:
        rds.describe_db_subnet_groups(DBSubnetGroupName=subnet_group_name)
        print(f"Subnet group {subnet_group_name} already exists.")
    except rds.exceptions.DBSubnetGroupNotFoundFault:
        rds.create_db_subnet_group(
            DBSubnetGroupName=subnet_group_name,
            DBSubnetGroupDescription="Subnet group for AWS PaaS demo RDS DB",
            SubnetIds=subnet_ids
        )
        print(f"Created subnet group: {subnet_group_name}")


def create_parameter_group(parameter_group_name, region):
    rds = boto3.client('rds', region_name=region)
    try:
        rds.describe_db_parameter_groups(DBParameterGroupName=parameter_group_name)
        print(f"Parameter group {parameter_group_name} already exists.")
    except rds.exceptions.DBParameterGroupNotFoundFault:
        rds.create_db_parameter_group(
            DBParameterGroupName=parameter_group_name,
            DBParameterGroupFamily='mysql8.0',
            Description="Parameter group for AWS PaaS demo RDS DB"
        )
        print(f"Created parameter group: {parameter_group_name}")


def add_inbound_rule(security_group_id, ip_address, region):
    ec2 = boto3.client('ec2', region_name=region)
    try:
        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='tcp',
            FromPort=3306,
            ToPort=3306,
            CidrIp=f'{ip_address}/32'
        )
        print(f"Added inbound rule to Security Group ID: {security_group_id} for IP: {ip_address}")
    except ec2.exceptions.ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print(f"Inbound rule for IP {ip_address} already exists in Security Group ID: {security_group_id}")


def remove_inbound_rule(security_group_id, ip_address, region):
    ec2 = boto3.client('ec2', region_name=region)
    ec2.revoke_security_group_ingress(
        GroupId=security_group_id,
        IpProtocol='tcp',
        FromPort=3306,
        ToPort=3306,
        CidrIp=f'{ip_address}/32'
    )
    print(f"Removed inbound rule from Security Group ID: {security_group_id} for IP: {ip_address}")


def run_sql_file(endpoint, username, password, db_name, sql_file_path):
    connection = pymysql.connect(
        host=endpoint,
        user=username,
        password=password,
        database=db_name
    )
    cursor = connection.cursor()

    with open(sql_file_path, 'r') as file:
        sql_commands = file.read().split(';')

    for command in sql_commands:
        if command.strip():
            cursor.execute(command)

    connection.commit()

    # Validate SQL execution by running "SHOW TABLES"
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    print("Tables in the database:", tables)

    cursor.close()
    connection.close()
    print("Executed SQL file successfully.")


region = 'ap-south-1'
secret_name = 'RDSDB_Credentials1'
db_instance_identifier = 'dmanup-aws-codecomit-demo-rdsdb'
db_instance_class = 'db.t3.micro'
engine = 'mysql'
db_name = 'accounts'
subnet_group_name = 'dmanup-aws-codecomit-demo-db-subnt'
parameter_group_name = 'dmanup-aws-codecomit-demo-rds-db-param-grp'

# Fetch credentials from Secrets Manager or create new ones
secret = get_or_create_secret(secret_name, region)
master_username = secret['username']
master_user_password = secret['password']

# Create or get the RDS instance
ec2 = boto3.client('ec2', region_name=region)
vpc_id = ec2.describe_vpcs()['Vpcs'][0]['VpcId']
subnet_ids = [subnet['SubnetId'] for subnet in
              ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']]

create_subnet_group(subnet_group_name, subnet_ids, region)
create_parameter_group(parameter_group_name, region)

# Fetch the security group ID
security_group = ec2.describe_security_groups(
    Filters=[{'Name': 'group-name', 'Values': ['dmanup-aws-codecomit-backend-secgrp']}])
if security_group['SecurityGroups']:
    security_group_id = security_group['SecurityGroups'][0]['GroupId']
    print(f"Security Group ID: {security_group_id}")
else:
    raise Exception("Security group 'dmanup-aws-codecomit-backend-secgrp' not found")

rds_endpoint = create_or_get_rds_instance(db_instance_identifier, db_instance_class, engine, master_username,
                                          master_user_password, db_name, subnet_group_name, security_group_id,
                                          parameter_group_name, region)

# Modify RDS instance to enable public access
modify_public_access(db_instance_identifier, True, region)

# Get public IP address
local_ip = requests.get('https://checkip.amazonaws.com').text.strip()

# Add inbound rule to security group for local IP
add_inbound_rule(security_group_id, local_ip, region)

# Run SQL file to set up the database
sql_file_path = os.path.join(os.getcwd(), 'src', 'main', 'resources', 'db_backup.sql')
run_sql_file(rds_endpoint, master_username, master_user_password, db_name, sql_file_path)

# Remove local IP from the security group
remove_inbound_rule(security_group_id, local_ip, region)

# Modify RDS instance to disable public access
modify_public_access(db_instance_identifier, False, region)
