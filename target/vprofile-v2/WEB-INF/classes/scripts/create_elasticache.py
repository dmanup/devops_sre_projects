import boto3
import json
import time


def create_or_get_elasticache_cluster(cluster_id, node_type, engine, num_cache_nodes, subnet_group_name,
                                      security_group_id, region):
    elasticache = boto3.client('elasticache', region_name=region)

    # Check if the Elasticache cluster already exists
    try:
        response = elasticache.describe_cache_clusters(CacheClusterId=cluster_id, ShowCacheNodeInfo=True)
        endpoint = response['CacheClusters'][0].get('CacheNodes', [{}])[0].get('Endpoint')
        if endpoint:
            print(
                f"Elasticache Cluster {cluster_id} already exists with endpoint: {endpoint['Address']}:{endpoint['Port']}")
            return endpoint
        else:
            print(f"Elasticache Cluster {cluster_id} already exists but endpoint information is not available yet.")
            return None
    except elasticache.exceptions.CacheClusterNotFoundFault:
        print(f"Elasticache Cluster {cluster_id} does not exist, creating a new one.")

    # Create the Elasticache cluster
    response = elasticache.create_cache_cluster(
        CacheClusterId=cluster_id,
        CacheNodeType=node_type,
        Engine=engine,
        NumCacheNodes=num_cache_nodes,
        CacheSubnetGroupName=subnet_group_name,
        SecurityGroupIds=[security_group_id],
        EngineVersion='1.6.17',
        Port=11211
    )

    # Wait for the cluster to become available
    while True:
        response = elasticache.describe_cache_clusters(CacheClusterId=cluster_id, ShowCacheNodeInfo=True)
        status = response['CacheClusters'][0]['CacheClusterStatus']
        print(f"Current Elasticache Cluster Status: {status}")
        if status == 'available':
            endpoint = response['CacheClusters'][0].get('CacheNodes', [{}])[0].get('Endpoint')
            if endpoint:
                print(
                    f"Elasticache Cluster {cluster_id} is now available with endpoint: {endpoint['Address']}:{endpoint['Port']}")
                return endpoint
            else:
                print(f"Elasticache Cluster {cluster_id} is available but endpoint information is not available yet.")
                return None
        time.sleep(30)


region = 'ap-south-1'
cluster_id = 'dmanup-aws-codecomit-demo-elasticache'
node_type = 'cache.t3.micro'
engine = 'memcached'
num_cache_nodes = 1
security_group_name = 'dmanup-aws-codecomit-backend-secgrp'
subnet_group_name = 'dmanup-aws-codecomit-demo-elasticache-subnet-group'

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

# Create the subnet group
elasticache = boto3.client('elasticache', region_name=region)
try:
    elasticache.describe_cache_subnet_groups(CacheSubnetGroupName=subnet_group_name)
    print(f"Subnet group {subnet_group_name} already exists.")
except elasticache.exceptions.CacheSubnetGroupNotFoundFault:
    elasticache.create_cache_subnet_group(
        CacheSubnetGroupName=subnet_group_name,
        CacheSubnetGroupDescription="Subnet group for AWS CodeCommit demo Elasticache",
        SubnetIds=subnet_ids
    )
    print(f"Created subnet group: {subnet_group_name}")

# Create or get the Elasticache cluster
create_or_get_elasticache_cluster(cluster_id, node_type, engine, num_cache_nodes, subnet_group_name, security_group_id,
                                  region)
