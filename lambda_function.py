"""
AWS Lambda Handler for Medium RSS Ingestion
This version is optimized for Lambda's constraints and execution model
"""

import boto3
import feedparser
import json
from datetime import datetime
import time
import os
from medium_feeds_config import ALL_FEEDS, TECH_FOCUSED, AIML_FOCUSED, BUSINESS_FOCUSED, DESIGN_FOCUSED

# Configuration from environment variables
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'medium-usecase-bucket')
S3_PREFIX = os.environ.get('S3_PREFIX', 'medium-rss-data/')
S3_MAIN_FILE = os.environ.get('S3_MAIN_FILE', 'medium_articles_master.json')

# Lambda has 15 minute timeout - limit feeds accordingly
MAX_FEEDS = int(os.environ.get('MAX_FEEDS', '30'))  # Safe for 15 min timeout
MIN_DELAY = float(os.environ.get('MIN_DELAY', '2'))
MAX_DELAY = float(os.environ.get('MAX_DELAY', '5'))

# Feed configuration - these can also be loaded from S3 or Parameter Store
SELECTED_FEEDS = AIML_FOCUSED

def download_existing_data(s3_client, bucket_name, s3_key):
    """Download existing JSON data from S3"""
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        json_data = response['Body'].read().decode('utf-8')
        data = json.loads(json_data)
        print(f"Downloaded existing data: {len(data.get('articles', []))} articles")
        return data
    except s3_client.exceptions.NoSuchKey:
        print("No existing data file found. Creating new structure.")
        return {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'total_ingestions': 0
            },
            'articles': [],
            'ingestion_history': []
        }

def ingest_single_rss(rss_url):
    """Parse a single Medium RSS feed"""
    try:
        feedparser.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        feed = feedparser.parse(rss_url)
        
        if hasattr(feed, 'bozo_exception'):
            error_msg = str(feed.bozo_exception)
            return [], False, f"Parse error: {error_msg[:50]}"
        
        if not feed.entries:
            return [], False, "No entries found"
        
        articles = []
        for entry in feed.entries:
            article = {
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'published': entry.get('published', ''),
                'author': entry.get('author', ''),
                'summary': entry.get('summary', ''),
                'tags': [tag.term for tag in entry.get('tags', [])],
                'id': entry.get('id', ''),
                'source_feed': rss_url,
                'first_seen': datetime.now().isoformat()
            }
            articles.append(article)
        
        return articles, True, None
        
    except Exception as e:
        return [], False, f"Error: {str(e)[:50]}"

def ingest_multiple_feeds(feed_urls, min_delay, max_delay):
    """Ingest from multiple RSS feeds"""
    import random
    
    all_articles = []
    seen_ids = set()
    stats = {
        'total_feeds': len(feed_urls),
        'successful': 0,
        'failed': 0,
        'articles_collected': 0
    }
    
    print(f"Starting ingestion of {len(feed_urls)} feeds...")
    
    for i, url in enumerate(feed_urls, 1):
        articles, success, error = ingest_single_rss(url)
        
        if success:
            stats['successful'] += 1
            for article in articles:
                if article['id'] not in seen_ids:
                    all_articles.append(article)
                    seen_ids.add(article['id'])
        else:
            stats['failed'] += 1
            print(f"Failed [{i}/{len(feed_urls)}]: {url} - {error}")
        
        # Rate limiting
        if i < len(feed_urls):
            time.sleep(random.uniform(min_delay, max_delay))
    
    stats['articles_collected'] = len(all_articles)
    print(f"Ingestion complete: {stats['successful']}/{stats['total_feeds']} successful, {stats['articles_collected']} articles")
    
    return all_articles, stats

def merge_articles(existing_data, new_articles):
    """Merge new articles into existing data"""
    existing_articles = existing_data.get('articles', [])
    existing_ids = {article['id']: idx for idx, article in enumerate(existing_articles)}
    
    new_count = 0
    updated_count = 0
    
    for new_article in new_articles:
        article_id = new_article['id']
        
        if article_id in existing_ids:
            idx = existing_ids[article_id]
            existing_articles[idx]['last_seen'] = datetime.now().isoformat()
            updated_count += 1
        else:
            new_article['last_seen'] = new_article['first_seen']
            existing_articles.append(new_article)
            new_count += 1
    
    return new_count, updated_count

def update_metadata(existing_data, new_count, updated_count, stats):
    """Update metadata"""
    metadata = existing_data.get('metadata', {})
    
    metadata['last_updated'] = datetime.now().isoformat()
    metadata['total_ingestions'] = metadata.get('total_ingestions', 0) + 1
    metadata['total_articles'] = len(existing_data['articles'])
    
    ingestion_record = {
        'timestamp': datetime.now().isoformat(),
        'feed_count': stats['total_feeds'],
        'successful_feeds': stats['successful'],
        'failed_feeds': stats['failed'],
        'new_articles': new_count,
        'updated_articles': updated_count,
        'total_after': len(existing_data['articles'])
    }
    
    if 'ingestion_history' not in existing_data:
        existing_data['ingestion_history'] = []
    
    existing_data['ingestion_history'].append(ingestion_record)
    
    if len(existing_data['ingestion_history']) > 100:
        existing_data['ingestion_history'] = existing_data['ingestion_history'][-100:]
    
    existing_data['metadata'] = metadata
    return existing_data

def upload_to_s3(s3_client, bucket_name, s3_key, data):
    """Upload data to S3"""
    json_data = json.dumps(data, indent=2, ensure_ascii=False)
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json_data,
        ContentType='application/json'
    )
    print(f"Uploaded to s3://{bucket_name}/{s3_key}")

def lambda_handler(event, context):
    """
    Main Lambda handler function
    
    Event structure (optional):
    {
        "feed_list": "SELECTED_FEEDS",  # or "ALL", or custom list
        "max_feeds": 30,
        "min_delay": 2,
        "max_delay": 5
    }
    """
    print("=" * 60)
    print("Medium RSS Lambda Ingestion Starting")
    print("=" * 60)
    
    # Get configuration from event or use defaults
    max_feeds = event.get('max_feeds', MAX_FEEDS) if event else MAX_FEEDS
    min_delay = event.get('min_delay', MIN_DELAY) if event else MIN_DELAY
    max_delay = event.get('max_delay', MAX_DELAY) if event else MAX_DELAY
    
    # Select feeds
    selected_feeds = SELECTED_FEEDS[:max_feeds]
    
    # Initialize S3 client
    s3_client = boto3.client('s3')
    s3_key = f"{S3_PREFIX}{S3_MAIN_FILE}"
    
    try:
        # Step 1: Download existing data
        print("\n[1/4] Downloading existing data...")
        existing_data = download_existing_data(s3_client, S3_BUCKET_NAME, s3_key)
        
        # Step 2: Ingest new articles
        print(f"\n[2/4] Ingesting from {len(selected_feeds)} feeds...")
        new_articles, stats = ingest_multiple_feeds(selected_feeds, min_delay, max_delay)
        
        if not new_articles:
            print("No articles collected")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No articles collected',
                    'stats': stats
                })
            }
        
        # Step 3: Merge
        print("\n[3/4] Merging articles...")
        new_count, updated_count = merge_articles(existing_data, new_articles)
        existing_data = update_metadata(existing_data, new_count, updated_count, stats)
        
        # Step 4: Upload
        print("\n[4/4] Uploading to S3...")
        upload_to_s3(s3_client, S3_BUCKET_NAME, s3_key, existing_data)
        
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Success',
                'new_articles': new_count,
                'updated_articles': updated_count,
                'total_articles': len(existing_data['articles']),
                'feeds_processed': stats['total_feeds'],
                'feeds_successful': stats['successful'],
                'feeds_failed': stats['failed']
            })
        }
        
        print("\n" + "=" * 60)
        print("Lambda execution completed successfully")
        print(f"New: {new_count}, Updated: {updated_count}, Total: {len(existing_data['articles'])}")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error',
                'error': str(e)
            })
        }

# For local testing
if __name__ == "__main__":
    # Test locally
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))