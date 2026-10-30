# EFS Filesystem for Model Storage
#
# Provides ReadWriteMany (RWX) storage for vLLM model weights.
# EFS supports concurrent access from multiple pods across AZs,
# enabling model serving scale-out.

resource "aws_efs_file_system" "models" {
  creation_token = "${var.cluster_name}-models"
  encrypted      = true

  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  tags = {
    Name = "${var.cluster_name}-models"
  }
}

# Security group allowing NFS access from within the VPC
resource "aws_security_group" "efs" {
  name_prefix = "${var.cluster_name}-efs-"
  description = "Allow NFS traffic from VPC for EFS"
  vpc_id      = aws_vpc.polar_sky.id

  ingress {
    description = "NFS from VPC"
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = {
    Name = "${var.cluster_name}-efs"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Mount targets in each private subnet (one per AZ required)
resource "aws_efs_mount_target" "private" {
  count = 2

  file_system_id  = aws_efs_file_system.models.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# StorageClass for EFS-backed PersistentVolumeClaims
resource "kubernetes_storage_class" "efs_retain" {
  metadata {
    name = "efs-polarsky-retain"
  }

  storage_provisioner = "efs.csi.aws.com"
  reclaim_policy      = "Retain"

  parameters = {
    provisioningMode = "efs-ap"
    fileSystemId     = aws_efs_file_system.models.id
    directoryPerms   = "700"
  }

  mount_options = ["iam"]
}
