import boto3
import json

# Set the region and repository details
REGION = "ap-south-1"
REPO_NAME = "dmanup-aws-codecommit-demo-repo"
BUILD_PROJECT_NAME = "dmanup-aws-codebuild-demo-project"
DEPLOY_APP_NAME = "dmanup-aws-codedeploy-demo-app"
DEPLOY_GROUP_NAME = "dmanup-aws-codedeploy-demo-group"
PIPELINE_NAME = "dmanup-aws-codepipeline-demo"
ARTIFACT_BUCKET = "dmanup-aws-codeartifact-bucket"

# Initialize boto3 clients
codecommit = boto3.client('codecommit', region_name=REGION)
codebuild = boto3.client('codebuild', region_name=REGION)
codedeploy = boto3.client('codedeploy', region_name=REGION)
codepipeline = boto3.client('codepipeline', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

# Function to create a CodeCommit repository
def create_codecommit_repo(repo_name):
    try:
        response = codecommit.create_repository(
            repositoryName=repo_name,
            repositoryDescription='Demo repository for AWS CodeCommit'
        )
        print(f"Created CodeCommit repository: {repo_name}")
    except codecommit.exceptions.RepositoryNameExistsException:
        print(f"CodeCommit repository {repo_name} already exists.")

# Function to create an S3 bucket for artifacts
def create_s3_bucket(bucket_name):
    try:
        s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': REGION})
        print(f"Created S3 bucket: {bucket_name}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"S3 bucket {bucket_name} already exists.")
    except s3.exceptions.BucketAlreadyExists:
        print(f"S3 bucket {bucket_name} already exists.")

# Function to create a CodeBuild project
def create_codebuild_project(project_name, artifact_bucket, role_arn):
    try:
        codebuild.create_project(
            name=project_name,
            source={'type': 'CODECOMMIT', 'location': f"https://git-codecommit.{REGION}.amazonaws.com/v1/repos/{REPO_NAME}"},
            artifacts={'type': 'S3', 'location': artifact_bucket},
            environment={
                'type': 'LINUX_CONTAINER',
                'image': 'aws/codebuild/standard:5.0',
                'computeType': 'BUILD_GENERAL1_SMALL',
                'environmentVariables': []
            },
            serviceRole=role_arn
        )
        print(f"Created CodeBuild project: {project_name}")
    except codebuild.exceptions.ResourceAlreadyExistsException:
        print(f"CodeBuild project {project_name} already exists.")

# Function to create a CodeDeploy application and deployment group
def create_codedeploy_app_and_group(app_name, group_name, role_arn):
    try:
        codedeploy.create_application(applicationName=app_name)
        print(f"Created CodeDeploy application: {app_name}")
    except codedeploy.exceptions.ApplicationAlreadyExistsException:
        print(f"CodeDeploy application {app_name} already exists.")

    # Create deployment group
    try:
        codedeploy.create_deployment_group(
            applicationName=app_name,
            deploymentGroupName=group_name,
            serviceRoleArn=role_arn,
            deploymentConfigName='CodeDeployDefault.OneAtATime',
            ec2TagFilters=[{'Key': 'Name', 'Value': 'CodeDeployDemo', 'Type': 'KEY_AND_VALUE'}],
            autoScalingGroups=[],
            deploymentStyle={'deploymentType': 'IN_PLACE', 'deploymentOption': 'WITHOUT_TRAFFIC_CONTROL'}
        )
        print(f"Created CodeDeploy deployment group: {group_name}")
    except codedeploy.exceptions.DeploymentGroupAlreadyExistsException:
        print(f"CodeDeploy deployment group {group_name} already exists.")

# Function to create a CodePipeline
def create_codepipeline(pipeline_name, role_arn, artifact_bucket):
    try:
        response = codepipeline.create_pipeline(
            pipeline={
                'name': pipeline_name,
                'roleArn': role_arn,
                'artifactStore': {'type': 'S3', 'location': artifact_bucket},
                'stages': [
                    {
                        'name': 'Source',
                        'actions': [
                            {
                                'name': 'Source',
                                'actionTypeId': {
                                    'category': 'Source',
                                    'owner': 'AWS',
                                    'provider': 'CodeCommit',
                                    'version': '1'
                                },
                                'outputArtifacts': [{'name': 'SourceOutput'}],
                                'configuration': {
                                    'RepositoryName': REPO_NAME,
                                    'BranchName': 'main',
                                    'PollForSourceChanges': 'false'  # Automatically trigger on changes
                                },
                                'runOrder': 1
                            }
                        ]
                    },
                    {
                        'name': 'Build',
                        'actions': [
                            {
                                'name': 'Build',
                                'actionTypeId': {
                                    'category': 'Build',
                                    'owner': 'AWS',
                                    'provider': 'CodeBuild',
                                    'version': '1'
                                },
                                'inputArtifacts': [{'name': 'SourceOutput'}],
                                'outputArtifacts': [{'name': 'BuildOutput'}],
                                'configuration': {'ProjectName': BUILD_PROJECT_NAME},
                                'runOrder': 1
                            }
                        ]
                    },
                    {
                        'name': 'Deploy',
                        'actions': [
                            {
                                'name': 'Deploy',
                                'actionTypeId': {
                                    'category': 'Deploy',
                                    'owner': 'AWS',
                                    'provider': 'CodeDeploy',
                                    'version': '1'
                                },
                                'inputArtifacts': [{'name': 'BuildOutput'}],
                                'configuration': {
                                    'ApplicationName': DEPLOY_APP_NAME,
                                    'DeploymentGroupName': DEPLOY_GROUP_NAME
                                },
                                'runOrder': 1
                            }
                        ]
                    }
                ]
            }
        )
        print(f"Created CodePipeline: {pipeline_name}")
    except codepipeline.exceptions.PipelineNameInUseException:
        print(f"CodePipeline {pipeline_name} already exists.")

# Create IAM roles for CodeBuild, CodeDeploy, and CodePipeline
def create_iam_role(role_name, policy_arn, service_principal):
    try:
        assume_role_policy_document = json.dumps({
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Principal': {'Service': service_principal},
                'Action': 'sts:AssumeRole'
            }]
        })
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=assume_role_policy_document,
        )
        iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        print(f"Created IAM Role: {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"IAM Role {role_name} already exists.")
    return f"arn:aws:iam::{boto3.client('sts').get_caller_identity().get('Account')}:role/{role_name}"

# Function to attach custom policy to the role
def attach_custom_policy_to_role(role_name, policy_name, policy_document):
    try:
        policy_response = iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_response['Policy']['Arn']
        )
        print(f"Attached custom policy {policy_name} to role {role_name}.")
    except iam.exceptions.EntityAlreadyExistsException:
        policy_arn = f"arn:aws:iam::{boto3.client('sts').get_caller_identity().get('Account')}:policy/{policy_name}"
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        print(f"Custom policy {policy_name} already exists and attached to role {role_name}.")

# Create CodeCommit repository
create_codecommit_repo(REPO_NAME)

# Create S3 bucket for artifacts
create_s3_bucket(ARTIFACT_BUCKET)

# Create IAM roles for CodeBuild, CodeDeploy, and CodePipeline
codebuild_role_arn = create_iam_role('codebuild-service-role', 'arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess', 'codebuild.amazonaws.com')
codedeploy_role_arn = create_iam_role('codedeploy-service-role', 'arn:aws:iam::aws:policy/service-role/AWSCodeDeployRole', 'codedeploy.amazonaws.com')
codepipeline_role_arn = create_iam_role('codepipeline-service-role', 'arn:aws:iam::aws:policy/AWSCodePipelineFullAccess', 'codepipeline.amazonaws.com')

# Attach custom policy to codepipeline-service-role
custom_policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "codecommit:GitPull",
                "codecommit:GetBranch",
                "codecommit:GetCommit",
                "codecommit:ListRepositories",
                "codecommit:ListBranches"
            ],
            "Resource": f"arn:aws:codecommit:{REGION}:{boto3.client('sts').get_caller_identity().get('Account')}:{REPO_NAME}"
        }
    ]
}
attach_custom_policy_to_role('codepipeline-service-role', 'CodePipelineCodeCommitAccessPolicy', custom_policy_document)

# Create CodeBuild project
create_codebuild_project(BUILD_PROJECT_NAME, ARTIFACT_BUCKET, codebuild_role_arn)

# Create CodeDeploy application and deployment group
create_codedeploy_app_and_group(DEPLOY_APP_NAME, DEPLOY_GROUP_NAME, codedeploy_role_arn)

# Create CodePipeline
create_codepipeline(PIPELINE_NAME, codepipeline_role_arn, ARTIFACT_BUCKET)
