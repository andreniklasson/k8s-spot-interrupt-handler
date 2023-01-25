import requests
import os
import subprocess
import time
import boto3
import sys
import json
import logging
from threading import Thread
import argparse

INSTANCE_ID_URL="http://169.254.169.254/latest/meta-data/instance-id"
TERMINATION_URL="http://169.254.169.254/latest/meta-data/spot/termination-time"
DOCUMENT_URL="http://169.254.169.254/latest/dynamic/instance-identity/document"
CAPACITY_REBALANCE_URL="http://169.254.169.254/latest/meta-data/events/recommendations/rebalance"
POLL_INTERVAL=5

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

document = requests.get(DOCUMENT_URL, timeout=10).text
region = json.loads(document)['region']
instance_id = requests.get(INSTANCE_ID_URL, timeout=10).text

asg_client = boto3.client('autoscaling', region_name=region)
elb_client = boto3.client('elbv2', region_name=region)

node_cordoned = False
prefer_no_schedule = False

def termination_notice():
    return requests.get(TERMINATION_URL).status_code == 200

def rebalance_recommendation():
    return requests.get(CAPACITY_REBALANCE_URL).status_code == 200

def drain_node(node_name):
    drain_cmd="kubectl drain " + node_name + " --force --ignore-daemonsets --delete-emptydir-data --grace-period=120"
    logging.info("Draining the node " + node_name)
    subprocess.Popen(drain_cmd, shell=True)

def cordon_node(node_name):
    drain_cmd="kubectl cordon " + node_name
    logging.info("Cordoning the node " + node_name)
    subprocess.Popen(drain_cmd, shell=True)

def uncordon_node(node_name):
    cordon_cmd="kubectl uncordon " + node_name
    logging.info("Uncordoning the node " + node_name)
    subprocess.Popen(cordon_cmd, shell=True)

def taint_node(node_name):
    taint_cmd="kubectl taint nodes " + node_name + " spot-interrupt-handler=owned:PreferNoSchedule"
    logging.info("Tainting the node with PreferNoSchedule " + node_name)
    subprocess.Popen(taint_cmd, shell=True)

def untaint_node(node_name):
    taint_cmd="kubectl taint nodes " + node_name + " spot-interrupt-handler=owned:PreferNoSchedule"
    logging.info("Untainting the node from PreferNoSchedule " + node_name)
    subprocess.Popen(taint_cmd, shell=True)

def handle_rebalance_cordon(node_name):
    global node_cordoned
    rebalancing = rebalance_recommendation()
    if(rebalancing and (not node_cordoned)):
        cordon_node(node_name)
        node_cordoned = True
    elif((not rebalancing) and node_cordoned):
        uncordon_node(node_name)
        node_cordoned = False

def handle_rebalance_taint(node_name):
    global prefer_no_schedule
    rebalancing = rebalance_recommendation()
    if(rebalancing and (not prefer_no_schedule)):
        taint_node(node_name)
        prefer_no_schedule = True
    elif((not rebalancing) and prefer_no_schedule):
        untaint_node(node_name)
        prefer_no_schedule = False

def fetch_autoscaling_group(instance_id):
    response = asg_client.describe_auto_scaling_groups()
    asg_groups = response["AutoScalingGroups"]
    while "NextToken" in response:
        response = asg_client.describe_auto_scaling_groups(
            NextToken=response["NextToken"]
        )
        asg_groups = asg_groups + response["AutoScalingGroups"]

    for autoscaling_group in asg_groups:
        for instance in autoscaling_group["Instances"]:
            if instance_id in instance["InstanceId"]:
                return autoscaling_group
    raise Exception("Did not find any autoscaling group matched to the instance id")

def detach_instance_from_asg(autoscaling_group, instance_id):
    try:
        asg_name = autoscaling_group["AutoScalingGroupName"]
        asg_client.detach_instances(
            InstanceIds=[
                instance_id,
            ],
            AutoScalingGroupName=asg_name,
            ShouldDecrementDesiredCapacity=False
        )
    except Exception as e:
        logging.error("Error trying to detach the instance from autoscaling group", e)

def deregister_from_elbs(instance_id):
    try:
        response = elb_client.describe_target_groups(
            PageSize=400
        )
        for target_group in response['TargetGroups']:
            print("Deregistering from target group " + target_group['TargetGroupArn'])
            elb_client.deregister_targets(
                TargetGroupArn = target_group['TargetGroupArn'],
                Targets=[
                    {
                        'Id': instance_id,
                    },
                ]
            )
    except Exception as e:
        logging.error("Error deregistering from ELB", e)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rebalancing-recommendation-cordon', action='store_true', dest="cordon")
    parser.add_argument('--rebalancing-recommendation-taint', action='store_true', dest="taint")
    parser.add_argument('--elb-deregistration', action='store_true', dest="elb")
    args = parser.parse_args()

    rebalance_cordon = args.cordon
    rebalance_taint = args.taint
    elb_deregister = args.elb

    logging.info("Starting interrupt handler.....")
    if "NODE_NAME" in os.environ:
        node_name = os.environ['NODE_NAME']
    else:
        logging.error("NODE_NAME ENV variable is not set! Exiting.....")
        sys.exit(1)

    try:
        autoscaling_group = fetch_autoscaling_group(instance_id)
    except Exception as e:
        logging.error("Unable to fetch autoscaling group", e)
        sys.exit(1)

    logging.info("Waiting for termination and rebalancing notice.....")
    while (not termination_notice()):
        if rebalance_cordon:
            handle_rebalance_cordon(node_name)
        elif rebalance_taint:
            handle_rebalance_taint(node_name)
        time.sleep( POLL_INTERVAL )

    logging.info("InstanceID: " + instance_id + " has reveived spot termination notice")

    cordon_node(node_name)

    logging.info("Detaching: " + instance_id + " from autoscaling group")
    Thread(target=detach_instance_from_asg, args=(autoscaling_group,instance_id,)).start()

    if elb_deregister:
        logging.info("Deregistering from elb")
        Thread(target=deregister_from_elbs, args=(instance_id,)).start()

    time.sleep( 30 )

    logging.info("Draining: " + node_name)
    drain_node(node_name)

    time.sleep( 500 )

if __name__ == "__main__":
    main()