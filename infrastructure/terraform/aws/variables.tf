variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "key_name" {
  description = "Name of an existing EC2 key pair (для SSH)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type (t3.micro може бути мало для збірки образів)"
  type        = string
  default     = "t3.medium"
}

variable "repo_url" {
  description = "Git URL проєкту для розгортання"
  type        = string
  default     = "https://github.com/YOUR_OWNER/CyberOps_PRO.git"
}

variable "repo_branch" {
  description = "Гілка, яка розгортається"
  type        = string
  default     = "master"
}

variable "ssh_cidr" {
  description = "CIDR, якому дозволено SSH"
  type        = string
  default     = "0.0.0.0/0"
}

variable "app_cidr" {
  description = "CIDR, якому дозволено доступ до портів застосунку"
  type        = string
  default     = "0.0.0.0/0"
}