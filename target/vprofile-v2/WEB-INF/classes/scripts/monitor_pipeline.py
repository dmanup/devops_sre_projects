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
    all_succeeded = True
    for stage in stages:
        stage_name = stage['stageName']
        if 'latestExecution' in stage:
            status = stage['latestExecution']['status']
            print(f"Stage: {stage_name}, Status: {status}")
            if status != 'Succeeded':
                all_succeeded = False
        else:
            print(f"Stage: {stage_name}, Status: Not started")
            all_succeeded = False
    return all_succeeded


print("Monitoring pipeline status...")
while True:
    if get_pipeline_status(PIPELINE_NAME):
        print("Pipeline execution succeeded.")
        break
    print("Pipeline execution in progress...")
    time.sleep(30)
