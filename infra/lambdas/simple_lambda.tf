# Simple Lambda Role with RDS IAM access
resource "aws_iam_role" "simple_lambda_role" {
  name = "${var.api_lambda_variables.project_name}-simple-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.api_lambda_variables.tags
}

# Simple Lambda policy for RDS IAM access
resource "aws_iam_policy" "simple_lambda_policy" {
  name = "${var.api_lambda_variables.project_name}-simple-lambda-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "rds-db:connect"
        ]
        Resource = "arn:aws:rds-db:${var.api_lambda_variables.aws_region}:${var.api_lambda_variables.caller_identity_account_id}:dbuser:${var.api_lambda_variables.aurora_cluster_identifier}/${var.api_lambda_variables.postgres_user}"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.api_lambda_variables.tags
}

resource "aws_iam_role_policy_attachment" "simple_lambda_policy" {
  policy_arn = aws_iam_policy.simple_lambda_policy.arn
  role       = aws_iam_role.simple_lambda_role.name
}

# Simple Lambda function
resource "aws_lambda_function" "simple_lambda" {
  function_name = "${var.api_lambda_variables.project_name}-simple-lambda"
  role          = aws_iam_role.simple_lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.13"
  timeout       = 30

  vpc_config {
    subnet_ids         = [var.api_lambda_variables.private_subnet_id]
    security_group_ids = [var.api_lambda_variables.lambda_security_group_id]
  }

  environment {
    variables = {
      RDS_ENDPOINT = var.api_lambda_variables.aurora_serverless_endpoint
      DB_NAME      = var.api_lambda_variables.postgres_db
      DB_USER      = var.api_lambda_variables.postgres_user
      REGION       = var.api_lambda_variables.aws_region
    }
  }

  filename         = "simple_lambda.zip"
  source_code_hash = data.archive_file.simple_lambda_zip.output_base64sha256

  tags = var.api_lambda_variables.tags
}

# Create a simple lambda deployment package
data "archive_file" "simple_lambda_zip" {
  type        = "zip"
  output_path = "simple_lambda.zip"
  source {
    content = <<EOF
import json
import boto3
import os

def handler(event, context):
    try:
        # Get RDS token for IAM authentication
        rds_client = boto3.client('rds')
        token = rds_client.generate_db_auth_token(
            DBHostname=os.environ['RDS_ENDPOINT'],
            Port=5432,
            DBUsername=os.environ['DB_USER'],
            Region=os.environ['REGION']
        )
        
        # Test database connection
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ['RDS_ENDPOINT'],
            port=5432,
            database=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=token,
            sslmode='require'
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully connected to Aurora Serverless',
                'rds_endpoint': os.environ['RDS_ENDPOINT'],
                'db_user': os.environ['DB_USER'],
                'db_version': db_version
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
EOF
    filename = "index.py"
  }
}