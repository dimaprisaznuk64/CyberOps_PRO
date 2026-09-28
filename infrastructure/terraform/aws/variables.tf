variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "key_name" {
  description = "Name of an existing EC2 key pair (для SSH)"
  type        = string
}

variable "admin_password" {
  description = "Пароль seed-адміністратора (пишеться в .env на інстансі)"
  type        = string
  sensitive   = true
  # Без дефолту свідомо: застосунок із admin/admin у публічному інтернеті —
  # це не демо, а діра. Terraform зупиниться на запиті, поки не задано.
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
  description = "CIDR, якому дозволено SSH (обов'язково: без дефолту, щоб 22 не відкрився в 0.0.0.0/0)"
  type        = string
}

variable "app_cidr" {
  description = "CIDR, якому дозволено доступ до портів застосунку (:8000 gateway, :3000 UI)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "app_public_url" {
  description = "Публічна адреса застосунку без порту, напр. https://cyberops.example.com. Порожньо = EIP інстансу (checkip у user-data)"
  type        = string
  default     = ""
}