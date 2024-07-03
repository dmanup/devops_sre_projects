import boto3


def create_security_group(group_name, description, vpc_id, region):
    ec2 = boto3.client('ec2', region_name=region)

    # Check if the security group already exists
    existing_sg = ec2.describe_security_groups(
        Filters=[{'Name': 'group-name', 'Values': [group_name]}]
    )

    if existing_sg['SecurityGroups']:
        security_group_id = existing_sg['SecurityGroups'][0]['GroupId']
        print(f"Security Group {group_name} already exists with ID: {security_group_id}")
    else:
        # Create the security group
        response = ec2.create_security_group(
            GroupName=group_name,
            Description=description,
            VpcId=vpc_id
        )
        security_group_id = response['GroupId']
        print(f"Created Security Group ID: {security_group_id}")

    # Check if the inbound rule already exists
    ingress_rules = ec2.describe_security_groups(GroupIds=[security_group_id])['SecurityGroups'][0]['IpPermissions']
    rule_exists = any(
        rule['IpProtocol'] == '-1' and
        any(group['GroupId'] == security_group_id for group in rule['UserIdGroupPairs'])
        for rule in ingress_rules
    )

    if rule_exists:
        print(f"Inbound rule already exists for Security Group ID: {security_group_id}")
    else:
        # Add inbound rule to allow all traffic within the same security group
        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': '-1',
                    'FromPort': -1,
                    'ToPort': -1,
                    'UserIdGroupPairs': [{'GroupId': security_group_id}]
                }
            ]
        )
        print(f"Added inbound rule to Security Group ID: {security_group_id}")

    return security_group_id


region = 'ap-south-1'
ec2 = boto3.client('ec2', region_name=region)
vpc_id = ec2.describe_vpcs()['Vpcs'][0]['VpcId']
security_group_id = create_security_group('dmanup-aws-codecomit-backend-secgrp',
                                          'Security group for backend of AWS PaaS demo', vpc_id, region)
