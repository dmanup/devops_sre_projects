import boto3
import time

# Set the region
REGION = "ap-south-1"

# Initialize boto3 clients
ec2 = boto3.client('ec2', region_name=REGION)
rds = boto3.client('rds', region_name=REGION)
mq = boto3.client('mq', region_name=REGION)
elasticache = boto3.client('elasticache', region_name=REGION)
elasticbeanstalk = boto3.client('elasticbeanstalk', region_name=REGION)
codecommit = boto3.client('codecommit', region_name=REGION)
codepipeline = boto3.client('codepipeline', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)


def delete_rds_instance(db_instance_identifier):
    try:
        rds.delete_db_instance(
            DBInstanceIdentifier=db_instance_identifier,
            SkipFinalSnapshot=True
        )
        print(f"Deleting RDS instance: {db_instance_identifier}")
        waiter = rds.get_waiter('db_instance_deleted')
        waiter.wait(DBInstanceIdentifier=db_instance_identifier)
        print(f"RDS instance {db_instance_identifier} deleted successfully.")
    except rds.exceptions.DBInstanceNotFoundFault:
        print(f"RDS instance {db_instance_identifier} not found.")


def delete_mq_broker(broker_id):
    try:
        mq.delete_broker(BrokerId=broker_id)
        print(f"Deleting MQ broker: {broker_id}")
        waiter = mq.get_waiter('broker_deleted')
        waiter.wait(BrokerId=broker_id)
        print(f"MQ broker {broker_id} deleted successfully.")
    except mq.exceptions.NotFoundException:
        print(f"MQ broker {broker_id} not found.")


def delete_elasticache_cluster(cluster_id):
    try:
        elasticache.delete_cache_cluster(CacheClusterId=cluster_id)
        print(f"Deleting Elasticache cluster: {cluster_id}")
        waiter = elasticache.get_waiter('cache_cluster_deleted')
        waiter.wait(CacheClusterId=cluster_id)
        print(f"Elasticache cluster {cluster_id} deleted successfully.")
    except elasticache.exceptions.CacheClusterNotFoundFault:
        print(f"Elasticache cluster {cluster_id} not found.")


def remove_inbound_rules_from_backend_sg(env_name, backend_security_group_name, region):
    # Fetch the Auto Scaling group name associated with the Elastic Beanstalk environment
    try:
        response = elasticbeanstalk.describe_environment_resources(
            EnvironmentName=env_name
        )
        auto_scaling_group_name = response['EnvironmentResources']['AutoScalingGroups'][0]['Name']
        print(f"AUTO_SCALING_GROUP_NAME: {auto_scaling_group_name}")
    except Exception as e:
        print(f"Error fetching Auto Scaling group: {e}")
        return

    # Fetch the instance IDs from the Auto Scaling group
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:aws:autoscaling:groupName', 'Values': [auto_scaling_group_name]}]
        )
        instance_ids = [instance['InstanceId'] for reservation in response['Reservations'] for instance in
                        reservation['Instances']]
        print(f"INSTANCE_IDS: {instance_ids}")
    except Exception as e:
        print(f"Error fetching instance IDs: {e}")
        return

    # Fetch the security group IDs associated with the instances
    security_group_ids = set()
    try:
        for instance_id in instance_ids:
            response = ec2.describe_instances(InstanceIds=[instance_id])
            security_groups = response['Reservations'][0]['Instances'][0]['SecurityGroups']
            for sg in security_groups:
                security_group_ids.add(sg['GroupId'])
        print(f"INSTANCE_SECURITY_GROUP_IDS: {security_group_ids}")
    except Exception as e:
        print(f"Error fetching security group IDs: {e}")
        return

    # Fetch the backend security group ID
    try:
        response = ec2.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': [backend_security_group_name]}]
        )
        if not response['SecurityGroups']:
            print(f"Backend security group {backend_security_group_name} not found.")
            return
        backend_security_group_id = response['SecurityGroups'][0]['GroupId']
        print(f"BACKEND_SECURITY_GROUP_ID: {backend_security_group_id}")
    except Exception as e:
        print(f"Error fetching backend security group ID: {e}")
        return

    # Remove inbound rules
    for sg_id in security_group_ids:
        try:
            ec2.revoke_security_group_ingress(
                GroupId=backend_security_group_id,
                IpPermissions=[
                    {'IpProtocol': 'tcp', 'FromPort': 3306, 'ToPort': 3306, 'UserIdGroupPairs': [{'GroupId': sg_id}]},
                    {'IpProtocol': 'tcp', 'FromPort': 11211, 'ToPort': 11211, 'UserIdGroupPairs': [{'GroupId': sg_id}]},
                    {'IpProtocol': 'tcp', 'FromPort': 5672, 'ToPort': 5672, 'UserIdGroupPairs': [{'GroupId': sg_id}]}
                ]
            )
            print(
                f"Removed inbound rules for security group ID: {sg_id} from backend security group ID: {backend_security_group_id}")
        except Exception as e:
            print(f"Error removing inbound rules for security group ID: {sg_id}: {e}")


def delete_elastic_beanstalk(env_name, app_name, backend_security_group_name):
    try:
        remove_inbound_rules_from_backend_sg(env_name, backend_security_group_name, REGION)
        elasticbeanstalk.terminate_environment(EnvironmentName=env_name)
        print(f"Terminating Elastic Beanstalk environment: {env_name}")
        while True:
            response = elasticbeanstalk.describe_environments(EnvironmentNames=[env_name])
            if not response['Environments']:
                print(f"Elastic Beanstalk environment {env_name} terminated successfully.")
                break
            status = response['Environments'][0]['Status']
            print(f"Current status: {status}")
            if status == 'Terminated':
                break
            time.sleep(30)
        elasticbeanstalk.delete_application(ApplicationName=app_name, TerminateEnvByForce=True)
        print(f"Deleted Elastic Beanstalk application: {app_name}")
    except elasticbeanstalk.exceptions.ResourceNotFoundException:
        print(f"Elastic Beanstalk environment or application {env_name} not found.")
    except Exception as e:
        print(f"Error terminating Elastic Beanstalk environment: {e}")


def delete_codecommit_repo(repo_name):
    try:
        codecommit.delete_repository(repositoryName=repo_name)
        print(f"Deleted CodeCommit repository: {repo_name}")
    except codecommit.exceptions.RepositoryDoesNotExistException:
        print(f"CodeCommit repository {repo_name} not found.")


def delete_codepipeline(pipeline_name):
    try:
        codepipeline.delete_pipeline(name=pipeline_name)
        print(f"Deleted CodePipeline: {pipeline_name}")
    except codepipeline.exceptions.PipelineNotFoundException:
        print(f"CodePipeline {pipeline_name} not found.")


def delete_s3_bucket(bucket_name):
    try:
        bucket = s3.Bucket(bucket_name)
        bucket.objects.all().delete()
        bucket.delete()
        print(f"Deleted S3 bucket: {bucket_name}")
    except s3.exceptions.NoSuchBucket:
        print(f"S3 bucket {bucket_name} not found.")
    except Exception as e:
        print(f"Error deleting S3 bucket {bucket_name}: {e}")


# Parameters
DB_INSTANCE_IDENTIFIER = "dmanup-aws-codecomit-demo-rdsdb"
BROKER_ID = "dmanup-aws-codecomit-demo-mq-broker"
CACHE_CLUSTER_ID = "dmanup-aws-codecomit-demo-elasticache"
ENV_NAME = "dmanup-aws-codecomit-demo-env"
APP_NAME = "dmanup-aws-codecomit-demo-app"
BACKEND_SECURITY_GROUP_NAME = "dmanup-demo-aws-paas-backend-secgrp"
REPO_NAME = "dmanup-aws-codecommit-demo-repo"
PIPELINE_NAME = "dmanup-aws-codepipeline-demo"
S3_BUCKET_NAME = "dmanup-aws-paas-demo-bucket"

# Delete components
delete_rds_instance(DB_INSTANCE_IDENTIFIER)
delete_mq_broker(BROKER_ID)
delete_elasticache_cluster(CACHE_CLUSTER_ID)
delete_elastic_beanstalk(ENV_NAME, APP_NAME, BACKEND_SECURITY_GROUP_NAME)
delete_codecommit_repo(REPO_NAME)
delete_codepipeline(PIPELINE_NAME)
delete_s3_bucket(S3_BUCKET_NAME)
