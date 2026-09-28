provider "aws" {
  region = var.region
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"]
}

resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

resource "aws_security_group" "cyberops" {
  name        = "cyberops-sg"
  description = "CyberOps Platform PRO: SSH + app ports"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.app_cidr]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.app_cidr]
  }

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.app_cidr]
  }

  # Фронтенд на :3000 — без цього правила UI на EC2 був просто недістянний
  # (compose його публікує, але SG не пропускав).
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.app_cidr]
  }

  # 16686 (Jaeger), 3001 (Grafana), 9090 (Prometheus) свідомо НЕ відкриті:
  # у compose вони слухають 127.0.0.1, а на сервері в них є власний
  # admin/admin. Доступ — через SSH-тунель (див. outputs і README).

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "cyberops" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.cyberops.id]

  user_data = templatefile("${path.module}/user-data.sh", {
    repo_url       = var.repo_url
    repo_branch    = var.repo_branch
    jwt_secret     = random_password.jwt_secret.result
    admin_password = var.admin_password
    app_public_url = var.app_public_url
  })

  tags = {
    Name = "cyberops"
  }
}

resource "aws_eip" "cyberops" {
  instance = aws_instance.cyberops.id
}

# Публічна адреса застосунку без порту: заданий домен або EIP інстансу.
# Використовується в outputs і (за бажання) у user-data.
locals {
  app_host = var.app_public_url != "" ? var.app_public_url : "http://${aws_eip.cyberops.public_ip}"
}