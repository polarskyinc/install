# Terraform Outputs for EKS Polar Sky Infrastructure

# EKS Cluster Information
output "eks_cluster_name" {
  description = "Name of the EKS cluster (use with kubectl commands)"
  value       = aws_eks_cluster.polar_sky.name
}

# kubectl Access Command
output "eks_update_kubeconfig_command" {
  description = "AWS CLI command to configure kubectl with EKS cluster credentials"
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.polar_sky.name}"
}

output "efs_filesystem_id" {
  description = "EFS filesystem ID used for model storage"
  value       = aws_efs_file_system.models.id
}
