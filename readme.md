# Python Spot Interrupt Handler
Given a spot termination notice, the spot-interrupt-handler detaches the instance from its associated Autoscaling group and drains the node for graceful pod termination.

## Arguments
- ```--elb-deregistration``` Deregisters the instance from the elb target groups that has the instance as a target. (Nice option if you are using aws-alb-ingress-controller)
- ```--rebalancing-recommendation-taint``` Taints the node with PreferNoSchedule upon a rebalance recommendation
- ```--rebalancing-recommendation-cordon``` Cordons the node upon a rebalance recommendation

### Node Selection
The DaemonSet utilizes nodeSelector to avoid having the handler running on your On Demand instances. Make sure your spot instances are labled with ```lifecycle=Ec2Spot```.

### Permissions
The interrupt-handler requires following IAM permissions to list and detach instances:

- "autoscaling:DescribeAutoScalingGroups"
- "autoscaling:DescribeAutoScalingInstances"
- "autoscaling:SetDesiredCapacity"
- "autoscaling:TerminateInstanceInAutoScalingGroup"
- "autoscaling:DetachInstances"
- "elasticloadbalancing:DeregisterTargets"
- "elasticloadbalancing:DescribeTags"
- "elasticloadbalancing:DescribeTargetGroupAttributes"
- "elasticloadbalancing:DescribeTargetGroups"

Recommended is to use IAM Roles for ServiceAccounts:
https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html 

### Build and deploy
Build the image using the Dockerfile present in the repo. Push the image to your ECR or other image registry. Modify the ImageUri value in _interrupt-handler.yaml_ to point towards your image. 

### Recommended resources
- https://ec2spotworkshops.com/
- https://github.com/mumoshu/kube-spot-termination-notice-handler