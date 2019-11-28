# Python Spot Interrupt Handler
Given a spot termination notice, the spot-interrupt-handler deregisters the instance from associated ELB Target Groups and drains the node for graceful pod termination.

### Node Selection
Label your nodes to avoid having the handler running on your On Demand instances. Label your Spot Instances with ```lifecycle=Ec2Spot``` and uncomment the nodeSelector block in the DaemonSet specified in _./interrupt-handler.yaml_.

### Target Groups Tags
The interrupt-handler identifies the associated Target Groups to be deregistred from with a given tag, namely ```spot-interrupt-handler/enabled : true```. 

### Permissions
The interrupt-handler requires following IAM permissions to deregister the instance from the Target Group:

- elasticloadbalancing:DeregisterTargets
- elasticloadbalancing:DescribeTags
- elasticloadbalancing:DescribeTargetGroupAttributes
- elasticloadbalancing:DescribeTargetGroups
- tag:GetResources

Recommended is to use resources like kube2iam, kiam, or newly released IAM Roles for ServiceAccounts:
https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html 

### Build and deploy
Build the image using the Dockerfile present in the repo. Push the image to your ECR or other image registry. Modify the ImageUri value in _interrupt-handler.yaml_ to point towards your image. 

### Recommended resources
- https://ec2spotworkshops.com/
- https://github.com/mumoshu/kube-spot-termination-notice-handler Does not deregister the instance from any load balancer, but the project inspired me