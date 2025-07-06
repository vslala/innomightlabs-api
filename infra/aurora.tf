# Aurora DSQL Cluster - Serverless with built-in IAM authentication
# Note: DSQL doesn't require database creation - connect directly to cluster
resource "aws_dsql_cluster" "innomightlabs_db" {
  deletion_protection_enabled = false

  tags = var.tags
}