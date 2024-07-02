import boto3
import time

# Set the region and pipeline name
REGION = "ap-south-1"
PIPELINE_NAME = "dmanup-aws-codepipeline-demo"

# Initialize boto3 client
codepipeline = boto3.client('codepipeline', region_name=REGION)


def get_pipeline_status(pipeline_name):
    response = codepipeline.get_pipeline_state(name=pipeline_name)
    stages = response['stageStates']
    for stage in stages:
        print(f"Stage: {stage['stageName']}, Status: {stage['latestExecution']['status']}")
    return all(stage['latestExecution']['status'] == 'Succeeded' for stage in stages)


print("Monitoring pipeline status...")
while True:
    if get_pipeline_status(PIPELINE_NAME):
        print("Pipeline execution succeeded.")
        break
    print("Pipeline execution in progress...")
    time.sleep(30)
