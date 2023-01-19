import requests
import os
import subprocess
import time
import boto3
import sys

INSTANCE_ID_URL="http://169.254.169.254/latest/meta-data/instance-id"
TERMINATION_URL="http://169.254.169.254/latest/meta-data/spot/termination-time"
DOCUMENT_URL="http://169.254.169.254/latest/dynamic/instance-identity/document"
CAPACITY_REBALANCE_URL="http://169.254.169.254/latest/meta-data/events/recommendations/rebalance"
POLL_INTERVAL=5

document = requests.get(DOCUMENT_URL, timeout=10).text
region = json.loads(document)['region']
instance_id = requests.get(INSTANCE_ID_URL, timeout=10).text

asg_client = boto3.client('autoscaling', region_name=region)

def wait_for_termination_notice():
    print("Polling " + TERMINATION_URL + " and " + CAPACITY_REBALANCE_URL + "every " + str(POLL_INTERVAL) + " second(s)")
    while requests.get(TERMINATION_URL).status_code != 200 and requests.get(CAPACITY_REBALANCE_URL).status_code != 200:
        time.sleep( POLL_INTERVAL )
    print("Interruption notice received!")

def drain_node(node_name):
    drain_cmd="kubectl drain " + node_name + " --force --ignore-daemonsets --delete-local-data --grace-period=120"
    print("Draining the node...")
    subprocess.Popen(drain_cmd, shell=True)

def fetch_autoscaling_group(instance_id):
    response = asg_client.describe_auto_scaling_groups()
    result_list = response["AutoScalingGroups"]
    while "NextToken" in response:
        response = asg_client.describe_auto_scaling_groups(
            NextToken=response["NextToken"]
        )
        result_list = result_list + response["AutoScalingGroups"]

    for autoscaling_group in result_list:
        for instance in autoscaling_group["Instances"]:
            if instance_id in instance["InstanceId"]:
                return autoscaling_group
    raise Exception("Did not find any autoscaling group matched to the instance id")

def detach_instance_from_asg(autoscaling_group, instance_id):
    asg_name = autoscaling_group["AutoScalingGroupName"]
    asg_client.detach_instances(
        InstanceIds=[
            instance_id,
        ],
        AutoScalingGroupName=asg_name,
        ShouldDecrementDesiredCapacity=False
    )

try:
    autoscaling_group = fetch_autoscaling_group(instance_id)
except Exception as e:
    print(e)
    sys.exit(1)

if "NODE_NAME" in os.environ:
    node_name = os.environ['NODE_NAME']
else:
    print("NODE_NAME ENV variable is not set! Exiting.....")
    sys.exit(1)

wait_for_termination_notice()
print("InstanceID: " + instance_id + " has reveived spot termination notice")

drain_node(node_name) # Runs as a parallel process
try:
    detach_instance_from_asg(autoscaling_group, instance_id)
except Exception as e:
    print("Error trying to detach the instance from autoscaling group")
    print(e)
time.sleep( 500 )