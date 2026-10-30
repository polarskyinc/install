# EKS Cluster and Node Groups
#
# Creates an EKS cluster with:
# - System node group: m5.xlarge (4 vCPU, 16 GiB) - on-demand, autoscaling 3-6
# - GPU node group: g4dn.{4,8,12}xlarge (T4) - spot, autoscaling with 100 GiB root volume

resource "aws_eks_cluster" "polar_sky" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.35"

  vpc_config {
    subnet_ids              = concat(aws_subnet.private[*].id, aws_subnet.public[*].id)
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_vpc_resource_controller,
  ]

  tags = {
    Name = var.cluster_name
  }
}

# System Node Group Launch Template - larger root volume for container images
resource "aws_launch_template" "system" {
  name_prefix = "${var.cluster_name}-system-"

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 50
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.cluster_name}-system"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# System Node Group - always-on, runs system pods
resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.polar_sky.name
  node_group_name = "system"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = aws_subnet.private[*].id

  instance_types = ["m5.xlarge"]
  capacity_type  = "ON_DEMAND"

  launch_template {
    id      = aws_launch_template.system.id
    version = aws_launch_template.system.latest_version
  }

  scaling_config {
    desired_size = 3
    min_size     = 3
    max_size     = 6
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry,
  ]

  tags = {
    Name                                            = "${var.cluster_name}-system"
    "k8s.io/cluster-autoscaler/enabled"             = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  }
}

# GPU Node Group Launch Template - larger root volume for vLLM container images
resource "aws_launch_template" "gpu" {
  name_prefix = "${var.cluster_name}-gpu-"

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.cluster_name}-gpu"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# GPU Node Group - autoscaling, runs vLLM model servers
resource "aws_eks_node_group" "gpu" {
  cluster_name    = aws_eks_cluster.polar_sky.name
  node_group_name = "gpu"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = aws_subnet.private[*].id

  instance_types = ["g4dn.4xlarge", "g4dn.8xlarge", "g4dn.12xlarge"]
  capacity_type  = var.gpu_node_capacity_type
  ami_type       = "AL2023_x86_64_NVIDIA"

  launch_template {
    id      = aws_launch_template.gpu.id
    version = aws_launch_template.gpu.latest_version
  }

  scaling_config {
    desired_size = var.gpu_node_min_count
    min_size     = var.gpu_node_min_count
    max_size     = var.gpu_node_max_count
  }

  labels = {
    "workload-type" = "gpu"
    "gpu-type"      = "t4"
  }

  taint {
    key    = "nvidia.com/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_container_registry,
  ]

  tags = {
    Name                                            = "${var.cluster_name}-gpu"
    "k8s.io/cluster-autoscaler/enabled"             = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  }
}
