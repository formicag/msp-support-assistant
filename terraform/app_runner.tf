# =============================================================================
# App Runner Service for Streamlit
# =============================================================================

# -----------------------------------------------------------------------------
# App Runner Service
# -----------------------------------------------------------------------------

resource "aws_apprunner_service" "streamlit" {
  service_name = "${local.name_prefix}-streamlit"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.streamlit.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = tostring(var.streamlit_port)

        runtime_environment_variables = {
          AWS_REGION            = var.aws_region
          ENVIRONMENT           = var.environment
          API_GATEWAY_ENDPOINT  = aws_apigatewayv2_stage.default.invoke_url
          SSM_PARAMETER_PREFIX  = "/${var.project_name}/${var.environment}"
          STREAMLIT_SERVER_PORT = tostring(var.streamlit_port)
        }
      }
    }

    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu               = var.streamlit_cpu
    memory            = var.streamlit_memory
    instance_role_arn = aws_iam_role.app_runner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/_stcore/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.streamlit.arn

  network_configuration {
    egress_configuration {
      egress_type = "DEFAULT"
    }
  }

  observability_configuration {
    observability_enabled = true
  }

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-streamlit"
  })

  depends_on = [
    aws_iam_role_policy_attachment.app_runner_ecr_access
  ]
}

# -----------------------------------------------------------------------------
# Auto Scaling Configuration
# -----------------------------------------------------------------------------

resource "aws_apprunner_auto_scaling_configuration_version" "streamlit" {
  auto_scaling_configuration_name = "${local.name_prefix}-streamlit-autoscaling"

  max_concurrency = 100
  max_size        = 5
  min_size        = 1

  tags = merge(local.cost_tags, {
    Name = "${local.name_prefix}-streamlit-autoscaling"
  })
}
