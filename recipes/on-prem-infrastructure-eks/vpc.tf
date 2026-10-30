# VPC and Networking for EKS Cluster
#
# Creates a VPC with public and private subnets across 2 AZs.
# Public subnets host the NAT gateway and load balancers.
# Private subnets host EKS nodes (system + GPU).

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  # Subnet CIDR allocation within the /16 VPC:
  # Public:  10.0.0.0/20, 10.0.16.0/20
  # Private: 10.0.128.0/20, 10.0.144.0/20
  public_subnets  = [cidrsubnet(var.vpc_cidr, 4, 0), cidrsubnet(var.vpc_cidr, 4, 1)]
  private_subnets = [cidrsubnet(var.vpc_cidr, 4, 8), cidrsubnet(var.vpc_cidr, 4, 9)]
}

resource "aws_vpc" "polar_sky" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "vpc-${var.cluster_name}"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "polar_sky" {
  vpc_id = aws_vpc.polar_sky.id

  tags = {
    Name = "igw-${var.cluster_name}"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.polar_sky.id
  cidr_block              = local.public_subnets[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                                        = "snet-public-${local.azs[count.index]}"
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# Private Subnets
resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.polar_sky.id
  cidr_block        = local.private_subnets[count.index]
  availability_zone = local.azs[count.index]

  tags = {
    Name                                        = "snet-private-${local.azs[count.index]}"
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# NAT Gateway (single, in first public subnet for cost savings)
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name = "eip-nat-${var.cluster_name}"
  }
}

resource "aws_nat_gateway" "polar_sky" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "nat-${var.cluster_name}"
  }

  depends_on = [aws_internet_gateway.polar_sky]
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.polar_sky.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.polar_sky.id
  }

  tags = {
    Name = "rt-public-${var.cluster_name}"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.polar_sky.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.polar_sky.id
  }

  tags = {
    Name = "rt-private-${var.cluster_name}"
  }
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}
