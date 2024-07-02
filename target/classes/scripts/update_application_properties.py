import boto3
import json


def get_secret(secret_name, region):
    client = boto3.client('secretsmanager', region_name=region)

    try:
        # Fetch the secret value
        secret_response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(secret_response['SecretString'])
        print(f"Fetched secret {secret_name} from AWS Secrets Manager.")
        return secret
    except client.exceptions.ResourceNotFoundException:
        print(f"Secret {secret_name} not found.")
        return None


def get_rds_endpoint(db_instance_identifier, region):
    rds = boto3.client('rds', region_name=region)
    try:
        response = rds.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)
        endpoint = response['DBInstances'][0]['Endpoint']['Address']
        print(f"Fetched RDS endpoint: {endpoint}")
        return endpoint
    except rds.exceptions.DBInstanceNotFoundFault:
        print(f"RDS instance {db_instance_identifier} not found.")
        return None


def get_mq_endpoint(broker_name, region):
    mq = boto3.client('mq', region_name=region)
    try:
        response = mq.describe_broker(BrokerId=broker_name)
        endpoint = response['BrokerInstances'][0]['Endpoints'][0]
        print(f"Fetched MQ endpoint: {endpoint}")
        return endpoint
    except mq.exceptions.NotFoundException:
        print(f"MQ broker {broker_name} not found.")
        return None


def get_cache_endpoint(cluster_id, region):
    elasticache = boto3.client('elasticache', region_name=region)
    try:
        response = elasticache.describe_cache_clusters(CacheClusterId=cluster_id, ShowCacheNodeInfo=True)
        endpoint = response['CacheClusters'][0]['CacheNodes'][0]['Endpoint']
        print(f"Fetched Cache endpoint: {endpoint['Address']}:{endpoint['Port']}")
        return endpoint
    except elasticache.exceptions.CacheClusterNotFoundFault:
        print(f"Elasticache cluster {cluster_id} not found.")
        return None


def update_properties_file(file_path, db_instance_identifier, broker_name, cache_cluster_id, region):
    rds_secret = get_secret('RDSDB_Credentials1', region)
    mq_secret = get_secret('RabbitMQ_Credentials', region)
    if not rds_secret or not mq_secret:
        print("Required secrets not found. Exiting.")
        return

    db_endpoint = get_rds_endpoint(db_instance_identifier, region)
    mq_endpoint = get_mq_endpoint(broker_name, region)
    cache_endpoint = get_cache_endpoint(cache_cluster_id, region)

    if not db_endpoint or not mq_endpoint or not cache_endpoint:
        print("Required components not found. Exiting.")
        return

    with open(file_path, 'r') as file:
        properties = file.readlines()

    # Update the properties
    new_properties = []
    for line in properties:
        if line.startswith("jdbc.url"):
            new_properties.append(
                f"jdbc.url=jdbc:mysql://{db_endpoint}:3306/accounts?useUnicode=true&characterEncoding=UTF-8&zeroDateTimeBehavior=convertToNull\n")
        elif line.startswith("jdbc.username"):
            new_properties.append(f"jdbc.username={rds_secret['username']}\n")
        elif line.startswith("jdbc.password"):
            new_properties.append(f"jdbc.password={rds_secret['password']}\n")
        elif line.startswith("memcached.active.host"):
            new_properties.append(f"memcached.active.host={cache_endpoint['Address']}\n")
        elif line.startswith("memcached.active.port"):
            new_properties.append(f"memcached.active.port={cache_endpoint['Port']}\n")
        elif line.startswith("rabbitmq.address"):
            new_properties.append(f"rabbitmq.address={mq_endpoint}\n")
        elif line.startswith("rabbitmq.username"):
            new_properties.append(f"rabbitmq.username={mq_secret['username']}\n")
        elif line.startswith("rabbitmq.password"):
            new_properties.append(f"rabbitmq.password={mq_secret['password']}\n")
        else:
            new_properties.append(line)

    with open(file_path, 'w') as file:
        file.writelines(new_properties)

    print(f"Updated {file_path} with new properties.")


region = 'ap-south-1'
db_instance_identifier = 'dmanup-aws-codecomit-demo-rdsdb'  # Replace with your actual RDS instance identifier
broker_name = 'dmanup-aws-codecomit-demo-mq-broker'  # Replace with your actual MQ broker name
cache_cluster_id = 'dmanup-aws-codecomit-demo-elasticache'  # Replace with your actual Cache cluster ID
file_path = 'D:/devops_articles/aws-code-commit/vprofile-project/src/main/resources/application.properties'

# Update the application properties file
update_properties_file(file_path, db_instance_identifier, broker_name, cache_cluster_id, region)
