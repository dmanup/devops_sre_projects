import boto3
import os
import subprocess

# Set the region and repository name
REGION = "ap-south-1"
REPO_NAME = "dmanup-aws-codecommit-demo-repo"
FILE_PATH = "D:/devops_articles/aws-code-commit/vprofile-project/src/main/resources/application.properties"

# Initialize boto3 client
codecommit = boto3.client('codecommit', region_name=REGION)

# Add a dummy comment line to the application.properties file
with open(FILE_PATH, 'a') as file:
    file.write("\n# Dummy comment added for testing pipeline trigger\n")
print("Added dummy comment to application.properties.")

# Commit the change to CodeCommit
commit_message = "Added dummy comment for testing pipeline trigger"
subprocess.run([
    "git", "add", FILE_PATH
])
subprocess.run([
    "git", "commit", "-m", commit_message
])

# Push the change to CodeCommit with upstream branch set
result = subprocess.run([
    "git", "push", "--set-upstream", "origin", "main"
], capture_output=True, text=True)

if result.returncode == 0:
    print("Committed and pushed the change to CodeCommit.")
else:
    print(f"Failed to push the change to CodeCommit: {result.stderr}")

print("Process finished with exit code", result.returncode)
