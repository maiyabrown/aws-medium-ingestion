"""
Article Indexing Lambda Function
Generates embeddings for Medium articles and creates searchable index
Triggered when medium_articles_master.json is updated in S3
"""

import json
import boto3
import os
from datetime import datetime
import pickle
import time
from typing import List, Dict
import hashlib

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)

# Configuration
S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
ARTICLES_KEY = os.environ.get('ARTICLES_KEY', 'medium-rss-data/medium_articles_master.json')
EMBEDDINGS_KEY = os.environ.get('EMBEDDINGS_KEY', 'embeddings/article_embeddings.pkl')
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'amazon.titan-embed-text-v1')
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '25'))  # Process in batches to avoid timeout

def generate_embedding(text: str) -> List[float]:
    """Generate embedding using Amazon Bedrock Titan"""
    try:
        body = json.dumps({"inputText": text[:8000]})  # Titan has 8K token limit
        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDING_MODEL,
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['embedding']
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise

def create_article_text(article: Dict) -> str:
    """Create searchable text from article metadata"""
    parts = [
        f"Title: {article.get('title', '')}",
        f"Author: {article.get('author', '')}",
        f"Summary: {article.get('summary', '')}",
        f"Tags: {', '.join(article.get('tags', [])[:10])}"
    ]
    return " ".join(parts)

def get_article_hash(article: Dict) -> str:
    """Generate hash for article to detect changes"""
    text = create_article_text(article)
    return hashlib.md5(text.encode()).hexdigest()

def load_existing_embeddings():
    """Load existing embeddings from S3"""
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=EMBEDDINGS_KEY)
        data = pickle.loads(response['Body'].read())
        print(f"Loaded existing embeddings: {len(data.get('embeddings', []))} items")
        return data
    except s3_client.exceptions.NoSuchKey:
        print("No existing embeddings found, creating new index")
        return {
            'embeddings': [],
            'article_ids': [],
            'article_hashes': {},
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error loading embeddings: {e}")
        return None

def save_embeddings(embeddings_data: Dict):
    """Save embeddings to S3"""
    try:
        embeddings_data['last_updated'] = datetime.now().isoformat()
        
        # Serialize and upload
        pickle_data = pickle.dumps(embeddings_data)
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=EMBEDDINGS_KEY,
            Body=pickle_data,
            ContentType='application/octet-stream'
        )
        
        print(f"Saved {len(embeddings_data['embeddings'])} embeddings to S3")
        
    except Exception as e:
        print(f"Error saving embeddings: {e}")
        raise

def process_articles(articles: List[Dict], existing_data: Dict) -> Dict:
    """
    Process articles and generate embeddings
    Only generates embeddings for new or changed articles
    """
    
    # Get existing data
    existing_embeddings = existing_data.get('embeddings', [])
    existing_ids = existing_data.get('article_ids', [])
    existing_hashes = existing_data.get('article_hashes', {})
    
    # Create maps for quick lookup
    id_to_index = {aid: i for i, aid in enumerate(existing_ids)}
    
    new_embeddings = []
    new_ids = []
    updated_hashes = {}
    
    stats = {
        'total': len(articles),
        'new': 0,
        'updated': 0,
        'unchanged': 0,
        'errors': 0
    }
    
    print(f"Processing {len(articles)} articles...")
    
    for i, article in enumerate(articles):
        article_id = article.get('id')
        if not article_id:
            stats['errors'] += 1
            continue
        
        # Calculate hash
        current_hash = get_article_hash(article)
        
        # Check if article needs embedding
        needs_embedding = False
        
        if article_id not in existing_hashes:
            # New article
            needs_embedding = True
            stats['new'] += 1
        elif existing_hashes.get(article_id) != current_hash:
            # Article was updated
            needs_embedding = True
            stats['updated'] += 1
        else:
            # Article unchanged, reuse existing embedding
            stats['unchanged'] += 1
            idx = id_to_index.get(article_id)
            if idx is not None and idx < len(existing_embeddings):
                new_embeddings.append(existing_embeddings[idx])
                new_ids.append(article_id)
                updated_hashes[article_id] = current_hash
                continue
        
        if needs_embedding:
            try:
                # Generate text and embedding
                text = create_article_text(article)
                embedding = generate_embedding(text)
                
                new_embeddings.append(embedding)
                new_ids.append(article_id)
                updated_hashes[article_id] = current_hash
                
                # Rate limiting
                if i % 10 == 0:
                    print(f"Processed {i}/{len(articles)} articles...")
                    time.sleep(0.5)  # Small delay to avoid rate limits
                
            except Exception as e:
                print(f"Error processing article {article_id}: {e}")
                stats['errors'] += 1
    
    print(f"\nProcessing complete:")
    print(f"  Total: {stats['total']}")
    print(f"  New: {stats['new']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Unchanged: {stats['unchanged']}")
    print(f"  Errors: {stats['errors']}")
    
    return {
        'embeddings': new_embeddings,
        'article_ids': new_ids,
        'article_hashes': updated_hashes,
        'created_at': existing_data.get('created_at', datetime.now().isoformat()),
        'stats': stats
    }

def lambda_handler(event, context):
    """
    Lambda handler for indexing articles
    Can be triggered by S3 event or manually
    """
    
    print(f"Indexing Lambda triggered")
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Load articles from S3
        print(f"Loading articles from s3://{S3_BUCKET}/{ARTICLES_KEY}")
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=ARTICLES_KEY)
        data = json.loads(response['Body'].read().decode('utf-8'))
        articles = data.get('articles', [])
        
        print(f"Found {len(articles)} articles")
        
        if not articles:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No articles to process'})
            }
        
        # Load existing embeddings
        existing_data = load_existing_embeddings()
        
        if existing_data is None:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to load existing embeddings'})
            }
        
        # Process articles and generate embeddings
        embeddings_data = process_articles(articles, existing_data)
        
        # Save to S3
        save_embeddings(embeddings_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Indexing complete',
                'stats': embeddings_data['stats'],
                'total_embeddings': len(embeddings_data['embeddings'])
            })
        }
        
    except Exception as e:
        print(f"Error in indexing Lambda: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Indexing failed'
            })
        }

# For manual testing
if __name__ == "__main__":
    # Test locally
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
