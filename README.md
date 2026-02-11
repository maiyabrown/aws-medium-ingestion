# Automated Ingestion of Medium Articles
This project established a scheduled job for ingesting Medium.com articles in AWS. The articles are ingested using their free and publicly available Medium RSS Feed.

AWS Services leveraged for this project include:
- [ ] Amazon Sagemaker AI: Code development
- [ ] AWS Cloudformation: Job Deployment
- [ ] AWS Lambda: Invoking the code
- [ ] Amazon Cloudwatch: Job monitoring
- [ ] Amazon S3: Data Storage

This script updates a single JSON file in S3 instead of creating new files each time. This guide also covers deploying the Medium RSS ingestion pipeline as an AWS Lambda function that runs automatically every 6 hours.

## Table of Contents
1. [How It Works](#how-it-works)
2. [Quick Start (CloudFormation)](#quick-start-cloudformation)
3. [Testing](#testing)
4. [Monitoring](#monitoring)
5. [Troubleshooting](#troubleshooting)


## How It Works

### Single Master File Approach
- **File**: `medium_articles_master.json` in your S3 bucket
- **Updates**: Appends new articles, updates existing ones
- **Backups**: Creates timestamped backups before each update


### Data Structure

```json
{
  "metadata": {
    "created_at": "2026-01-27T10:00:00",
    "last_updated": "2026-01-27T15:30:00",
    "total_ingestions": 5,
    "total_articles": 1250
  },
  "articles": [
    {
      "id": "article-unique-id",
      "title": "Article Title",
      "link": "https://medium.com/...",
      "author": "Author Name",
      "published": "2026-01-27T09:00:00",
      "summary": "Article summary...",
      "tags": ["python", "ai"],
      "source_feed": "https://medium.com/feed/tag/python",
      "first_seen": "2026-01-27T10:00:00",
      "last_seen": "2026-01-27T15:30:00"
    }
  ],
  "ingestion_history": [
    {
      "timestamp": "2026-01-27T15:30:00",
      "feed_count": 50,
      "new_articles": 25,
      "updated_articles": 10,
      "total_after": 1250
    }
  ]
}
```

## Key Features

### 1. **Deduplication**
- Uses article IDs to prevent duplicates
- New articles are added
- Existing articles get `last_seen` timestamp updated

### 2. **Automatic Backups**
- Creates timestamped backup before each update
- Format: `medium_articles_master_backup_YYYYMMDD_HHMMSS.json`
- Keeps your data safe

### 3. **Tracking**
- `first_seen`: When article was first ingested
- `last_seen`: Last time article appeared in feeds
- Ingestion history with statistics

### 4. **Growth Over Time**
Running daily for a month:
- Day 1: ~500 articles
- Day 7: ~1,500 articles (new + recurring)
- Day 30: ~3,000-5,000 articles


## Usage

### Basic Usage
```bash
python medium_incremental_ingestion.py
```


### Configuration
Edit the script to customize:

```python
# Choose your bucket
S3_BUCKET_NAME = "your-medium-data-bucket"

# Choose your feeds
SELECTED_FEEDS = TECH_FOCUSED  # or ALL_FEEDS, BUSINESS_FOCUSED, etc.

# Master file name (single file that gets updated)
S3_MAIN_FILE = "medium_articles_master.json"
```


## Example Output

```
====================================================
Medium RSS Incremental Ingestion Pipeline
====================================================

[1/6] Setting up S3 bucket...
✓ Bucket my-medium-bucket already exists

[2/6] Creating backup of existing data...
✓ Created backup: s3://my-medium-bucket/medium-rss-data/medium_articles_master_backup_20260127_153045.json

[3/6] Downloading existing data from S3...
✓ Downloaded existing data: 1000 articles

[4/6] Ingesting articles from 50 feeds...
Progress: 10/50 feeds (95 unique articles so far)
Progress: 20/50 feeds (187 unique articles so far)
...
✓ Ingestion complete!
  Total unique articles: 485

[5/6] Merging new articles with existing data...

📊 Merge Results:
  New articles added: 125
  Existing articles updated: 360
  Total articles in dataset: 1125

[6/6] Uploading updated data to S3...
✓ Updated s3://my-medium-bucket/medium-rss-data/medium_articles_master.json

📈 Dataset Statistics:
  Total articles: 1125
  Total ingestions: 6
  Created: 2026-01-20T10:00:00
  Last updated: 2026-01-27T15:30:45
  Unique authors: 487

  Top 10 tags:
    - python: 234
    - artificial-intelligence: 198
    - machine-learning: 187
    - data-science: 165
    - javascript: 142
    ...

====================================================
✓ Pipeline completed successfully!
====================================================
Location: s3://my-medium-bucket/medium-rss-data/medium_articles_master.json
====================================================
```

## Quick Start (CloudFormation)

### Option 1: Deploy via AWS Console

1. **Upload CloudFormation Template**
   ```
   - Go to AWS CloudFormation Console
   - Click "Create stack" → "With new resources"
   - Upload cloudformation-template.yaml
   ```

2. **Configure Parameters**
   ```
   S3BucketName: my-medium-data-bucket (must be globally unique)
   ScheduleExpression: rate(6 hours)
   MaxFeeds: 30
   ```

3. **Create Stack**
   - Review and create
   - Wait for stack creation to complete (~2-3 minutes)

4. **Upload Lambda Code**
   ```bash
   # Build deployment package
   ./build_lambda.sh
   
   # Update Lambda function
   aws lambda update-function-code \
     --function-name MediumRSSIngestion \
     --zip-file fileb://lambda_deployment.zip
   ```

### Option 2: Deploy via AWS CLI (my preference)

```bash
# 1. Create stack
aws cloudformation create-stack \
  --stack-name medium-rss-ingestion \
  --template-body file://cloudformation-template.yaml \
  --parameters \
    ParameterKey=S3BucketName,ParameterValue=my-medium-data-bucket \
    ParameterKey=ScheduleExpression,ParameterValue="rate(6 hours)" \
    ParameterKey=MaxFeeds,ParameterValue=30 \
  --capabilities CAPABILITY_IAM

# 2. Wait for stack creation
aws cloudformation wait stack-create-complete \
  --stack-name medium-rss-ingestion

# 3. Build and upload Lambda code
./build_lambda.sh

aws lambda update-function-code \
  --function-name MediumRSSIngestion \
  --zip-file fileb://lambda_deployment.zip
```


## Testing

### Test Lambda Manually

**Via AWS Console:**
1. Go to Lambda → Functions → MediumRSSIngestion
2. Click "Test" tab
3. Create test event (use default empty JSON: `{}`)
4. Click "Test"
5. Check execution results

**Via AWS CLI:**
```bash
aws lambda invoke \
  --function-name MediumRSSIngestion \
  --payload '{}' \
  response.json

# View results
cat response.json | jq
```

### Check S3 Output

```bash
# List files in bucket
aws s3 ls s3://my-medium-data-bucket/medium-rss-data/

# Download and view the data
aws s3 cp s3://my-medium-data-bucket/medium-rss-data/medium_articles_master.json ./

# Check article count
cat medium_articles_master.json | jq '.articles | length'
```

### View Logs

**Via Console:**
- Go to CloudWatch → Log groups
- Find `/aws/lambda/MediumRSSIngestion`
- View latest log stream

**Via CLI:**
```bash
# Get recent logs
aws logs tail /aws/lambda/MediumRSSIngestion --follow
```

---

## Monitoring

### CloudWatch Metrics

View Lambda metrics:
- Invocations
- Duration
- Errors
- Throttles

```bash
# Get recent invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=MediumRSSIngestion \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

### Set Up Alarms

Get notified if Lambda fails:

```bash
# Create SNS topic for alerts
aws sns create-topic --name MediumRSSAlerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:MediumRSSAlerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Create CloudWatch alarm
aws cloudwatch put-metric-alarm \
  --alarm-name MediumRSSLambdaErrors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 3600 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=MediumRSSIngestion \
  --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:MediumRSSAlerts
```

---


## Troubleshooting

### Lambda Times Out (15 minutes)

**Problem:** Too many feeds for 15-minute limit

**Solution:** Reduce MAX_FEEDS
```bash
# Update to process fewer feeds
aws lambda update-function-configuration \
  --function-name MediumRSSIngestion \
  --environment Variables="{...,MAX_FEEDS=20,...}"
```

### Rate Limiting Errors

**Problem:** All feeds failing with 403/429

**Solution:** Run less frequently
```bash
# Change to every 12 hours
aws events put-rule \
  --name MediumRSSIngestionSchedule \
  --schedule-expression "rate(12 hours)"
```

### No Data in S3

**Checklist:**
1. Check Lambda execution logs
2. Verify S3 bucket name in environment variables
3. Check IAM permissions
4. Test Lambda manually

```bash
# View recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/MediumRSSIngestion \
  --filter-pattern "ERROR"
```

### Permission Denied

**Problem:** Lambda can't write to S3

**Solution:** Check IAM role
```bash
# Verify role has S3 permissions
aws iam get-role-policy \
  --role-name MediumRSSLambdaRole \
  --policy-name S3Access
```
