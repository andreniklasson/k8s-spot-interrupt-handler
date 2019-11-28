import requests
import os
import subprocess
import time
import boto3
import json

INSTANCE_ID_URL="http://169.254.169.254/latest/meta-data/instance-id"
TERMINATION_URL="http://169.254.169.254/latest/meta-data/spot/termination-time"
DOCUMENT_URL="http://169.254.169.254/latest/dynamic/instance-identity/document"

POLL_INTERVAL=5

instanceId = requests.get(INSTANCE_ID_URL).text
print("InstanceID: " + instanceId)

document = requests.get(DOCUMENT_URL).text
region = document['region']
print("Region: " + region)

resourceClient = boto3.client('resourcegroupstaggingapi', region_name=region)
elbClient = boto3.client('elbv2', region_name=region)

print("Polling " + TERMINATION_URL + " every " + str(POLL_INTERVAL) + " second(s)")
while requests.get(TERMINATION_URL).status_code is not 200:
    time.sleep( POLL_INTERVAL )
    print("Status: alive")

## Deregistering from ELB
try:
    resourceResponse = resourceClient.get_resources(
        TagFilters=[
            {
                'Key': 'spot-interrupt-handler/enabled',
                'Values': [
                    'true',
                ]
            },
        ],
        ResourcesPerPage=100,
        ResourceTypeFilters=[
            'elasticloadbalancing:targetgroup',
        ]
    )
    for targetGroupArn in resourceResponse['ResourceTagMappingList']:
        print(targetGroupArn['ResourceARN'])
        elbResponse = elbClient.deregister_targets(
            TargetGroupArn = targetGroupArn['ResourceARN'],
            Targets=[
                {
                    'Id': instanceId,
                },
            ]
        )
except:
    print("Error deregistering from ELB")

## Drain the node
nodeCmd="kubectl --namespace " + os.environ['NAMESPACE'] + " get pod "+ os.environ['POD_NAME'] +" --output jsonpath=\"{.spec.nodeName}\""
nodeName = subprocess.check_output(nodeCmd, shell=True).decode('ascii')

drainCmd="kubectl drain " + nodeName + " --force --ignore-daemonsets --delete-local-data"
print(drainCmd)
res = subprocess.check_output(drainCmd, shell=True).decode('ascii')
print(res)

time.sleep( 500 )

