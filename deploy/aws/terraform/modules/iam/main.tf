# ── App Runner instance role ──────────────────────────────────────────────────
# Attached to the running App Runner container — what the API can DO

resource "aws_iam_role" "app_runner_instance" {
  name = "bookforge-app-runner-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "app_runner_instance_policy" {
  name = "bookforge-app-runner-instance-policy"
  role = aws_iam_role.app_runner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Read secrets from Secrets Manager
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:*:${var.account_id}:secret:bookforge/*"
      },
      {
        # Write compiled books to S3
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
        Resource = "${var.s3_bucket}/*"
      },
      {
        # List books in S3
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = var.s3_bucket
      },
      {
        # Launch Fargate worker tasks — scoped to bookforge task definition only
        Effect   = "Allow"
        Action   = ["ecs:RunTask", "ecs:DescribeTasks", "ecs:StopTask"]
        Resource = [
          "arn:aws:ecs:*:${var.account_id}:task-definition/bookforge-worker*",
          "arn:aws:ecs:*:${var.account_id}:task/bookforge/*",
        ]
      },
      {
        # Pass roles to ECS tasks — scoped to specific fargate roles only
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [
          "arn:aws:iam::${var.account_id}:role/bookforge-fargate-execution",
          "arn:aws:iam::${var.account_id}:role/bookforge-fargate-task",
        ]
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      }
    ]
  })
}

# ── App Runner access role ────────────────────────────────────────────────────
# Allows App Runner SERVICE (not container) to pull from ECR

resource "aws_iam_role" "app_runner_access" {
  name = "bookforge-app-runner-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "app_runner_ecr" {
  role       = aws_iam_role.app_runner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ── Fargate task execution role ───────────────────────────────────────────────
# What ECS AGENT can do: pull images, write logs

resource "aws_iam_role" "fargate_execution" {
  name = "bookforge-fargate-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "fargate_execution_basic" {
  role       = aws_iam_role.fargate_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "fargate_execution_secrets" {
  name = "bookforge-fargate-execution-secrets"
  role = aws_iam_role.fargate_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:aws:secretsmanager:*:${var.account_id}:secret:bookforge/*"
    }]
  })
}

# ── Fargate task role ─────────────────────────────────────────────────────────
# What the WORKER CONTAINER can do

resource "aws_iam_role" "fargate_task" {
  name = "bookforge-fargate-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "fargate_task_policy" {
  name = "bookforge-fargate-task-policy"
  role = aws_iam_role.fargate_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:*:${var.account_id}:secret:bookforge/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
        Resource = "${var.s3_bucket}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = var.s3_bucket
      },
      {
        # Write logs
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}
