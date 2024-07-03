import boto3
import json
import time
import os

# Set the region
REGION = "ap-south-1"

# Initialize boto3 clients
ec2 = boto3.client('ec2', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
elasticbeanstalk = boto3.client('elasticbeanstalk', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)

# Get AWS account ID
AWS_ACCOUNT_ID = sts.get_caller_identity()["Account"]

KEY_PAIR_NAME = "dmanup-aws-codecomit-demo-keypair"
KEY_PAIR_FILE = f"{KEY_PAIR_NAME}.pem"
LOCAL_PATH = "D:/devops_articles/aws-code-commit/vprofile-project/target/vprofile-v2.war"
S3_BUCKET = "dmanup-aws-codecomit-demo-bucket"
S3_KEY = "vprofile-v2.war"
DESTINATION_PATH = f"s3://{S3_BUCKET}/{S3_KEY}"

# Create or use existing key pair
try:
    ec2.describe_key_pairs(KeyNames=[KEY_PAIR_NAME])
    print(f"Key pair already exists: {KEY_PAIR_NAME}")
except ec2.exceptions.ClientError:
    key_pair = ec2.create_key_pair(KeyName=KEY_PAIR_NAME)
    with open(KEY_PAIR_FILE, 'w') as file:
        file.write(key_pair['KeyMaterial'])
    os.chmod(KEY_PAIR_FILE, 0o400)
    print(f"Created key pair: {KEY_PAIR_NAME}")

# Fetch the default VPC ID
DEFAULT_VPC_ID = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])['Vpcs'][0]['VpcId']
print(f"Fetched Default VPC ID: {DEFAULT_VPC_ID}")

# Fetch the subnet IDs for the default VPC
subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [DEFAULT_VPC_ID]}])['Subnets']
SUBNET_IDS = ",".join([subnet['SubnetId'] for subnet in subnets])
print(f"Fetched Subnet IDs: {SUBNET_IDS}")

# Create or use existing S3 bucket
try:
    s3.head_bucket(Bucket=S3_BUCKET)
    print(f"S3 bucket already exists: {S3_BUCKET}")
except s3.exceptions.ClientError:
    s3.create_bucket(Bucket=S3_BUCKET, CreateBucketConfiguration={'LocationConstraint': REGION})
    print(f"Created S3 bucket: {S3_BUCKET}")

# Create or use existing IAM Role for Elastic Beanstalk Service
try:
    iam.get_role(RoleName="aws-elasticbeanstalk-service-role")
    print("IAM Role already exists: aws-elasticbeanstalk-service-role")
except iam.exceptions.NoSuchEntityException:
    iam.create_role(
        RoleName="aws-elasticbeanstalk-service-role",
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "elasticbeanstalk.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    print("Created IAM Role: aws-elasticbeanstalk-service-role")

# Attach the AWS managed policies to the service role
iam.attach_role_policy(RoleName="aws-elasticbeanstalk-service-role", PolicyArn="arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth")
iam.attach_role_policy(RoleName="aws-elasticbeanstalk-service-role", PolicyArn="arn:aws:iam::aws:policy/AWSElasticBeanstalkManagedUpdatesCustomerRolePolicy")
print("Attached policies to IAM Role: aws-elasticbeanstalk-service-role")

# Create or use existing Instance Profile for Elastic Beanstalk EC2 Instances
try:
    iam.get_instance_profile(InstanceProfileName="aws-elasticbeanstalk-ec2-role")
    print("Instance Profile already exists: aws-elasticbeanstalk-ec2-role")
except iam.exceptions.NoSuchEntityException:
    iam.create_instance_profile(InstanceProfileName="aws-elasticbeanstalk-ec2-role")
    print("Created Instance Profile: aws-elasticbeanstalk-ec2-role")

# Create or use existing IAM Role for EC2 Instances
try:
    iam.get_role(RoleName="aws-elasticbeanstalk-ec2-role")
    print("IAM Role already exists: aws-elasticbeanstalk-ec2-role")
except iam.exceptions.NoSuchEntityException:
    iam.create_role(
        RoleName="aws-elasticbeanstalk-ec2-role",
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    print("Created IAM Role: aws-elasticbeanstalk-ec2-role")

# Attach the AWS managed policies to the instance role
iam.attach_role_policy(RoleName="aws-elasticbeanstalk-ec2-role", PolicyArn="arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier")
iam.attach_role_policy(RoleName="aws-elasticbeanstalk-ec2-role", PolicyArn="arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier")
print("Attached policies to IAM Role: aws-elasticbeanstalk-ec2-role")

# Attach the role to the instance profile
instance_profiles = iam.list_instance_profiles_for_role(RoleName="aws-elasticbeanstalk-ec2-role")['InstanceProfiles']
if not any(profile['InstanceProfileName'] == "aws-elasticbeanstalk-ec2-role" for profile in instance_profiles):
    iam.add_role_to_instance_profile(InstanceProfileName="aws-elasticbeanstalk-ec2-role", RoleName="aws-elasticbeanstalk-ec2-role")
    print("Attached Role to Instance Profile: aws-elasticbeanstalk-ec2-role")
else:
    print("Role already attached to Instance Profile: aws-elasticbeanstalk-ec2-role")

# Create an Elastic Beanstalk application
try:
    elasticbeanstalk.create_application(
        ApplicationName="dmanup-aws-codecomit-demo-app",
        Description="Demo application for AWS PaaS"
    )
    print("Created Elastic Beanstalk Application: dmanup-aws-codecomit-demo-app")
except elasticbeanstalk.exceptions.TooManyApplicationsException:
    print("Elastic Beanstalk Application already exists: dmanup-aws-codecomit-demo-app")

# Upload the application code to S3
s3.upload_file(LOCAL_PATH, S3_BUCKET, S3_KEY)
print(f"Uploaded application code to S3: {DESTINATION_PATH}")

# Create an application version
elasticbeanstalk.create_application_version(
    ApplicationName="dmanup-aws-codecomit-demo-app",
    VersionLabel="v1",
    SourceBundle={
        "S3Bucket": S3_BUCKET,
        "S3Key": S3_KEY
    }
)
print("Created Application Version: v1")

# Create the configuration options file
options = [
    {
        "Namespace": "aws:autoscaling:launchconfiguration",
        "OptionName": "InstanceType",
        "Value": "t3.micro"
    },
    {
        "Namespace": "aws:autoscaling:launchconfiguration",
        "OptionName": "EC2KeyName",
        "Value": KEY_PAIR_NAME
    },
    {
        "Namespace": "aws:elasticbeanstalk:environment",
        "OptionName": "EnvironmentType",
        "Value": "LoadBalanced"
    },
    {
        "Namespace": "aws:autoscaling:asg",
        "OptionName": "MinSize",
        "Value": "2"
    },
    {
        "Namespace": "aws:autoscaling:asg",
        "OptionName": "MaxSize",
        "Value": "3"
    },
    {
        "Namespace": "aws:autoscaling:trigger",
        "OptionName": "MeasureName",
        "Value": "NetworkOut"
    },
    {
        "Namespace": "aws:autoscaling:trigger",
        "OptionName": "Statistic",
        "Value": "Average"
    },
    {
        "Namespace": "aws:autoscaling:trigger",
        "OptionName": "Unit",
        "Value": "Bytes"
    },
    {
        "Namespace": "aws:autoscaling:trigger",
        "OptionName": "Period",
        "Value": "300"
    },
    {
        "Namespace": "aws:autoscaling:trigger",
        "OptionName": "BreachDuration",
        "Value": "300"
    },
    {
        "Namespace": "aws:ec2:vpc",
        "OptionName": "VPCId",
        "Value": DEFAULT_VPC_ID
    },
    {
        "Namespace": "aws:ec2:vpc",
        "OptionName": "Subnets",
        "Value": SUBNET_IDS
    },
    {
        "Namespace": "aws:elasticbeanstalk:environment:process:default",
        "OptionName": "StickinessEnabled",
        "Value": "true"
    },
    {
        "Namespace": "aws:elasticbeanstalk:environment:process:default",
        "OptionName": "StickinessLBCookieDuration",
        "Value": "86400"
    },
    {
        "Namespace": "aws:elasticbeanstalk:environment:process:default",
        "OptionName": "HealthCheckPath",
        "Value": "/login"
    },
    {
        "Namespace": "aws:elasticbeanstalk:healthreporting:system",
        "OptionName": "SystemType",
        "Value": "basic"
    },
    {
        "Namespace": "aws:elasticbeanstalk:application",
        "OptionName": "Application Healthcheck URL",
        "Value": "/login"
    },
    {
        "Namespace": "aws:elasticbeanstalk:managedactions",
        "OptionName": "ManagedActionsEnabled",
        "Value": "false"
    },
    {
        "Namespace": "aws:elasticbeanstalk:command",
        "OptionName": "DeploymentPolicy",
        "Value": "Rolling"
    },
    {
        "Namespace": "aws:elasticbeanstalk:command",
        "OptionName": "BatchSizeType",
        "Value": "Fixed"
    },
    {
        "Namespace": "aws:elasticbeanstalk:command",
        "OptionName": "BatchSize",
        "Value": "1"
    },
    {
        "Namespace": "aws:elasticbeanstalk:sns:topics",
        "OptionName": "Notification Endpoint",
        "Value": "anupde@gmail.com"
    },
    {
        "Namespace": "aws:elasticbeanstalk:environment",
        "OptionName": "ServiceRole",
        "Value": "aws-elasticbeanstalk-service-role"
    },
    {
        "Namespace": "aws:autoscaling:launchconfiguration",
        "OptionName": "IamInstanceProfile",
        "Value": "aws-elasticbeanstalk-ec2-role"
    }
]

with open('options.json', 'w') as file:
    json.dump(options, file)
print("Created Configuration Options file: options.json")

# Get the solution stack name for the Elastic Beanstalk environment
solution_stack_name = next(
    stack for stack in elasticbeanstalk.list_available_solution_stacks()['SolutionStacks']
    if "64bit Amazon Linux 2" in stack and "Corretto 11" in stack and "Tomcat 8.5" in stack
)
print(f"Solution Stack Name/Platform version:{solution_stack_name}")

# Create an Elastic Beanstalk environment
elasticbeanstalk.create_environment(
    ApplicationName="dmanup-aws-codecomit-demo-app",
    EnvironmentName="dmanup-aws-codecomit-demo-env",
    SolutionStackName=solution_stack_name,
    OptionSettings=json.load(open('options.json')),
    VersionLabel="v1",
    Tier={
        "Name": "WebServer",
        "Type": "Standard",
        "Version": "1.0"
    }
)
print("Created Elastic Beanstalk Environment: dmanup-aws-codecomit-demo-env")

# Wait until the environment is available
print("Waiting for the Elastic Beanstalk environment to become available...")
while True:
    env_status = elasticbeanstalk.describe_environments(
        ApplicationName="dmanup-aws-codecomit-demo-app",
        EnvironmentNames=["dmanup-aws-codecomit-demo-env"]
    )['Environments'][0]['Status']
    print(f"Current Environment Status: {env_status}")
    if env_status == "Ready":
        break
    time.sleep(30)
print("Elastic Beanstalk environment is now available")

# Check if the application was created successfully
app_status = elasticbeanstalk.describe_applications(
    ApplicationNames=["dmanup-aws-codecomit-demo-app"]
)['Applications'][0]['ApplicationName']
print(f"Application Status: {app_status}")

# Check if the environment was created successfully
env_status = elasticbeanstalk.describe_environments(
    ApplicationName="dmanup-aws-codecomit-demo-app",
    EnvironmentNames=["dmanup-aws-codecomit-demo-env"]
)['Environments'][0]['Status']
print(f"Environment Status: {env_status}")
