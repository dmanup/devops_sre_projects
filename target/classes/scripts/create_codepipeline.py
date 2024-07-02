import boto3
import json
import time

# Set the region
REGION = "ap-south-1"

# Initialize boto3 clients
codecommit = boto3.client('codecommit', region_name=REGION)
codebuild = boto3.client('codebuild', region_name=REGION)
codepipeline = boto3.client('codepipeline', region_name=REGION)
iam = boto3.client('iam', region_name=REGION)
elasticbeanstalk = boto3.client('elasticbeanstalk', region_name=REGION)
sts = boto3.client('sts', region_name=REGION)

# Get AWS account ID
AWS_ACCOUNT_ID = sts.get_caller_identity()["Account"]

# Create CodeCommit repository
repo_name = "dmanup-aws-codecommit-demo-repo"
try:
    codecommit.create_repository(repositoryName=repo_name)
    print(f"Created CodeCommit repository: {repo_name}")
except codecommit.exceptions.RepositoryNameExistsException:
    print(f"CodeCommit repository already exists: {repo_name}")

# Create IAM Role for CodeBuild
build_role_name = "codebuild-service-role"
try:
    iam.get_role(RoleName=build_role_name)
    print(f"IAM Role already exists: {build_role_name}")
except iam.exceptions.NoSuchEntityException:
    iam.create_role(
        RoleName=build_role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "codebuild.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    print(f"Created IAM Role: {build_role_name}")
    iam.attach_role_policy(RoleName=build_role_name, PolicyArn="arn:aws:iam::aws:policy/AWSCodeBuildAdminAccess")
    print(f"Attached AWSCodeBuildAdminAccess policy to IAM Role: {build_role_name}")

# Create CodeBuild project
build_project_name = "dmanup-aws-codebuild-demo-project"
source = {
    "type": "CODECOMMIT",
    "location": f"https://git-codecommit.{REGION}.amazonaws.com/v1/repos/{repo_name}"
}
artifacts = {
    "type": "NO_ARTIFACTS"
}
environment = {
    "type": "LINUX_CONTAINER",
    "image": "aws/codebuild/standard:4.0",
    "computeType": "BUILD_GENERAL1_SMALL"
}
service_role = f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/{build_role_name}"
try:
    codebuild.create_project(
        name=build_project_name,
        source={"type": "CODECOMMIT", "location": source["location"]},
        artifacts=artifacts,
        environment=environment,
        serviceRole=service_role
    )
    print(f"Created CodeBuild project: {build_project_name}")
except codebuild.exceptions.ResourceAlreadyExistsException:
    print(f"CodeBuild project already exists: {build_project_name}")

# Create IAM Role for CodePipeline
pipeline_role_name = "codepipeline-service-role"
try:
    iam.get_role(RoleName=pipeline_role_name)
    print(f"IAM Role already exists: {pipeline_role_name}")
except iam.exceptions.NoSuchEntityException:
    iam.create_role(
        RoleName=pipeline_role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "codepipeline.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )
    print(f"Created IAM Role: {pipeline_role_name}")

    # Wait for a few seconds to ensure the role is fully created
    time.sleep(10)

    iam.attach_role_policy(RoleName=pipeline_role_name, PolicyArn="arn:aws:iam::aws:policy/AWSCodePipelineFullAccess")
    print(f"Attached AWSCodePipelineFullAccess policy to IAM Role: {pipeline_role_name}")

# Create CodePipeline
pipeline_name = "dmanup-aws-codepipeline-demo"
pipeline_role_arn = f"arn:aws:iam::{AWS_ACCOUNT_ID}:role/{pipeline_role_name}"
pipeline = {
    "name": pipeline_name,
    "roleArn": pipeline_role_arn,
    "artifactStore": {
        "type": "S3",
        "location": "dmanup-aws-paas-demo-bucket"
    },
    "stages": [
        {
            "name": "Source",
            "actions": [
                {
                    "name": "Source",
                    "actionTypeId": {
                        "category": "Source",
                        "owner": "AWS",
                        "provider": "CodeCommit",
                        "version": "1"
                    },
                    "outputArtifacts": [
                        {"name": "SourceOutput"}
                    ],
                    "configuration": {
                        "RepositoryName": repo_name,
                        "BranchName": "main"
                    }
                }
            ]
        },
        {
            "name": "Build",
            "actions": [
                {
                    "name": "Build",
                    "actionTypeId": {
                        "category": "Build",
                        "owner": "AWS",
                        "provider": "CodeBuild",
                        "version": "1"
                    },
                    "inputArtifacts": [
                        {"name": "SourceOutput"}
                    ],
                    "outputArtifacts": [
                        {"name": "BuildOutput"}
                    ],
                    "configuration": {
                        "ProjectName": build_project_name
                    }
                }
            ]
        },
        {
            "name": "Deploy",
            "actions": [
                {
                    "name": "Deploy",
                    "actionTypeId": {
                        "category": "Deploy",
                        "owner": "AWS",
                        "provider": "ElasticBeanstalk",
                        "version": "1"
                    },
                    "inputArtifacts": [
                        {"name": "BuildOutput"}
                    ],
                    "configuration": {
                        "ApplicationName": "dmanup-aws-paas-demo-app",
                        "EnvironmentName": "dmanup-aws-paas-demo-env"
                    }
                }
            ]
        }
    ]
}
try:
    codepipeline.create_pipeline(pipeline=pipeline)
    print(f"Created CodePipeline: {pipeline_name}")
except codepipeline.exceptions.PipelineNameInUseException:
    print(f"CodePipeline already exists: {pipeline_name}")
