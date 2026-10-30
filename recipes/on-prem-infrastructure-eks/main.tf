provider "aws" {
  region = var.region

  default_tags {
    tags = var.tags
  }
}

provider "kubernetes" {
  host                   = aws_eks_cluster.polar_sky.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.polar_sky.certificate_authority[0].data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.polar_sky.name]
  }
}

provider "helm" {
  kubernetes {
    host                   = aws_eks_cluster.polar_sky.endpoint
    cluster_ca_certificate = base64decode(aws_eks_cluster.polar_sky.certificate_authority[0].data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.polar_sky.name]
    }
  }
}
