output "public_ip" {
  description = "Публічна IP інстансу"
  value       = aws_eip.cyberops.public_ip
}

output "ssh_command" {
  description = "Команда SSH для входу"
  value       = "ssh -i <your-key.pem> ubuntu@${aws_eip.cyberops.public_ip}"
}

output "gateway_url" {
  description = "URL API Gateway циберопс-платформи (:8000)"
  value       = "${local.app_host}:8000"
}

output "frontend_url" {
  description = "URL UI Next.js (:3000)"
  value       = "${local.app_host}:3000"
}

output "observability_ssh_tunnel" {
  description = "Спостерігаємий стек слухає 127.0.0.1 — доступ через SSH-тунель (Grafana/Jaeger/Prometheus у SG не відкриті)"
  value = join("; ", [
    "ssh -N -L 3001:localhost:3001 -L 16686:localhost:16686 -L 9090:9090 <key.pem>@${aws_eip.cyberops.public_ip}",
    "Grafana http://localhost:3001, Jaeger http://localhost:16686, Prometheus http://localhost:9090",
  ])
}