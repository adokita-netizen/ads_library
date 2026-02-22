# ==================== VPC ====================

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.name_prefix}-vpc" }
}

# ==================== Subnets ====================

resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = { Name = "${local.name_prefix}-public-1" }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}c"
  map_public_ip_on_launch = true

  tags = { Name = "${local.name_prefix}-public-2" }
}

resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.aws_region}a"

  tags = { Name = "${local.name_prefix}-private-1" }
}

resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.aws_region}c"

  tags = { Name = "${local.name_prefix}-private-2" }
}

# ==================== Internet Gateway ====================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${local.name_prefix}-igw" }
}

# ==================== NAT Instance (t4g.nano, ~$3/月) ====================

data "aws_ami" "al2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = { Name = "${local.name_prefix}-nat-eip" }
}

resource "aws_instance" "nat" {
  ami                    = data.aws_ami.al2023_arm64.id
  instance_type          = var.nat_instance_type
  subnet_id              = aws_subnet.public_1.id
  vpc_security_group_ids = [aws_security_group.nat.id]
  source_dest_check      = false
  iam_instance_profile   = aws_iam_instance_profile.nat.name

  user_data = <<-EOF
    #!/bin/bash
    set -ex

    # Enable IP forwarding immediately
    echo 1 > /proc/sys/net/ipv4/ip_forward
    echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.d/99-nat.conf
    sysctl -p /etc/sysctl.d/99-nat.conf

    # Detect the primary network interface dynamically
    IFACE=$(ip -o link show | awk -F': ' '/state UP/{print $2}' | grep -v lo | head -1)

    # NAT masquerade using nftables (Amazon Linux 2023 default)
    dnf install -y nftables
    systemctl enable nftables
    systemctl start nftables

    nft add table nat
    nft add chain nat postrouting '{ type nat hook postrouting priority 100 ; }'
    nft add rule nat postrouting oifname "$IFACE" masquerade

    nft add table inet filter
    nft add chain inet filter forward '{ type filter hook forward priority 0 ; policy accept ; }'

    # Persist nftables rules
    nft list ruleset > /etc/nftables/nat.nft
    echo 'include "/etc/nftables/nat.nft"' >> /etc/sysconfig/nftables.conf
  EOF

  user_data_replace_on_change = true

  tags = { Name = "${local.name_prefix}-nat-instance" }
}

resource "aws_eip_association" "nat" {
  instance_id   = aws_instance.nat.id
  allocation_id = aws_eip.nat.id
}

# ==================== Route Tables ====================

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${local.name_prefix}-public-rt" }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block           = "0.0.0.0/0"
    network_interface_id = aws_instance.nat.primary_network_interface_id
  }

  tags = { Name = "${local.name_prefix}-private-rt" }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# ==================== S3 VPC Gateway Endpoint (free) ====================

resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.aws_region}.s3"

  route_table_ids = [
    aws_route_table.public.id,
    aws_route_table.private.id,
  ]

  tags = { Name = "${local.name_prefix}-s3-endpoint" }
}
