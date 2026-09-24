output "public_ip" {
  description = "Публічна IP інстансу"
  value       = aws_eip.cyberops.public_ip
}

output "ssh_command" {
  description = "Команда SSH для входу"
  value       = "ssh -i <your-key.pem> ubuntu@${aws_eip.cyberops.public_ip}"
}

output "gateway_url" {
  description = "URL API Gateway циберопс-платформи"
  value       = "http://${aws_eip.cyberops.public_ip}:8000"
}