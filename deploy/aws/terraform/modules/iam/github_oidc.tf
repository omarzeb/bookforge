# GitHub OIDC provider — allows GitHub Actions to assume AWS roles
# without long-lived access keys (issue #8)

data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
}

resource "aws_iam_role" "github_deploy" {
  name = "bookforge-github-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          # Restrict to main branch of your repo only
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy_policy" {
  name = "bookforge-github-deploy-policy"
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Push images to ECR
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ]
        Resource = [
          "arn:aws:ecr:*:${var.account_id}:repository/bookforge-api",
          "arn:aws:ecr:*:${var.account_id}:repository/bookforge-worker",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        # Update App Runner service
        Effect   = "Allow"
        Action   = ["apprunner:UpdateService", "apprunner:ListServices", "apprunner:DescribeService"]
        Resource = "arn:aws:apprunner:*:${var.account_id}:service/bookforge-api/*"
      },
      {
        # Register new ECS task definition
        Effect   = "Allow"
        Action   = ["ecs:RegisterTaskDefinition", "ecs:DescribeTaskDefinition"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [
          "arn:aws:iam::${var.account_id}:role/bookforge-fargate-execution",
          "arn:aws:iam::${var.account_id}:role/bookforge-fargate-task",
        ]
      }
    ]
  })
}
