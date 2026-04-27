"""
RAG Chatbot Lambda Function
Handles chat queries using Amazon Bedrock and FAISS vector search
"""

import json
import boto3
import os
from datetime import datetime
import numpy as np
from typing import List, Dict, Any
import pickle

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb')

# Configuration from environment
S3_BUCKET = os.environ.get('S3_BUCKET_NAME', 'your-medium-data-bucket')
ARTICLES_KEY = os.environ.get('ARTICLES_KEY', 'medium-rss-data/medium_articles_master.json')
EMBEDDINGS_KEY = os.environ.get('EMBEDDINGS_KEY', 'embeddings/article_embeddings.pkl')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'ChatHistory')
MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'amazon.titan-embed-text-v1')
TOP_K = int(os.environ.get('TOP_K', '5'))

# Global cache for embeddings (loaded once per Lambda container)
_embeddings_cache = None
_articles_cache = None

def load_articles_from_s3() -> List[Dict]:
    """Load Medium articles from S3"""
    global _articles_cache
    
    if _articles_cache is not None:
        return _articles_cache
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=ARTICLES_KEY)
        data = json.loads(response['Body'].read().decode('utf-8'))
        _articles_cache = data.get('articles', [])
        print(f"Loaded {len(_articles_cache)} articles from S3")
        return _articles_cache
    except Exception as e:
        print(f"Error loading articles: {e}")
        return []

def load_embeddings_from_s3():
    """Load pre-computed embeddings and FAISS index from S3"""
    global _embeddings_cache
    
    if _embeddings_cache is not None:
        return _embeddings_cache
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=EMBEDDINGS_KEY)
        _embeddings_cache = pickle.loads(response['Body'].read())
        print(f"Loaded embeddings cache with {len(_embeddings_cache.get('embeddings', []))} items")
        return _embeddings_cache
    except s3_client.exceptions.NoSuchKey:
        print("No embeddings found - index needs to be built")
        return None
    except Exception as e:
        print(f"Error loading embeddings: {e}")
        return None

def generate_embedding(text: str) -> List[float]:
    """Generate embedding using Amazon Bedrock Titan"""
    try:
        body = json.dumps({"inputText": text})
        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDING_MODEL,
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['embedding']
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def search_similar_articles(query_embedding: List[float], top_k: int = TOP_K) -> List[Dict]:
    """Search for similar articles using embeddings"""
    embeddings_data = load_embeddings_from_s3()
    articles = load_articles_from_s3()
    
    if not embeddings_data or not articles:
        return []
    
    # Get embeddings and article IDs
    stored_embeddings = embeddings_data.get('embeddings', [])
    article_ids = embeddings_data.get('article_ids', [])
    
    if len(stored_embeddings) == 0:
        return []
    
    # Calculate similarities
    query_vec = np.array(query_embedding)
    similarities = []
    
    for i, emb in enumerate(stored_embeddings):
        sim = cosine_similarity(query_vec, np.array(emb))
        similarities.append((sim, article_ids[i]))
    
    # Sort by similarity and get top-k
    similarities.sort(reverse=True, key=lambda x: x[0])
    top_results = similarities[:top_k]
    
    # Get full article data
    article_map = {article['id']: article for article in articles}
    results = []
    
    for sim_score, article_id in top_results:
        if article_id in article_map:
            article = article_map[article_id].copy()
            article['similarity_score'] = float(sim_score)
            results.append(article)
    
    return results

def construct_prompt(query: str, context_articles: List[Dict], conversation_history: List[Dict] = None) -> str:
    """Construct prompt with context for Claude"""
    
    # Build context from articles
    context_parts = []
    for i, article in enumerate(context_articles, 1):
        context_parts.append(f"""
Article {i}:
Title: {article.get('title', 'N/A')}
Author: {article.get('author', 'N/A')}
Published: {article.get('published', 'N/A')}
Summary: {article.get('summary', 'N/A')[:500]}
Tags: {', '.join(article.get('tags', [])[:5])}
Link: {article.get('link', 'N/A')}
""")
    
    context = "\n".join(context_parts)
    
    # Build conversation history if provided
    history = ""
    if conversation_history:
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            history += f"{role}: {content}\n\n"
    
    # Construct final prompt
    prompt = f"""You are a helpful AI assistant that answers questions about Medium articles. You have access to a collection of Medium articles and can help users find information, summarize content, and answer questions based on these articles.

Here are the most relevant articles for the current query:

{context}

{'Previous conversation:' + chr(10) + history if history else ''}

User question: {query}

Please provide a helpful, accurate answer based on the provided articles. If the articles don't contain enough information to answer the question, say so. Always cite which articles you're referencing by including their titles and links in your response."""

    return prompt

def call_claude(prompt: str) -> Dict[str, Any]:
    """Call Amazon Bedrock Claude model"""
    try:
        # Prepare request for Claude 3
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "top_p": 0.9
        })
        
        response = bedrock_runtime.invoke_model(
            modelId=MODEL_ID,
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        
        # Extract text from Claude 3 response format
        content = response_body.get('content', [])
        if content and len(content) > 0:
            text = content[0].get('text', '')
        else:
            text = "I apologize, but I couldn't generate a response."
        
        return {
            'text': text,
            'usage': response_body.get('usage', {})
        }
        
    except Exception as e:
        print(f"Error calling Claude: {e}")
        raise

def save_to_dynamodb(session_id: str, query: str, response: str, context_articles: List[Dict]):
    """Save chat interaction to DynamoDB"""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        item = {
            'sessionId': session_id,
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'response': response,
            'context_articles': [
                {
                    'title': a.get('title', ''),
                    'link': a.get('link', ''),
                    'similarity': a.get('similarity_score', 0)
                }
                for a in context_articles[:3]  # Store top 3
            ],
            'ttl': int(datetime.now().timestamp()) + (30 * 24 * 60 * 60)  # 30 days
        }
        
        table.put_item(Item=item)
        print(f"Saved interaction for session: {session_id}")
        
    except Exception as e:
        print(f"Error saving to DynamoDB: {e}")
        # Don't fail the request if DynamoDB fails

def get_chat_history(session_id: str, limit: int = 10) -> List[Dict]:
    """Retrieve chat history from DynamoDB"""
    try:
        table = dynamodb.Table(DYNAMODB_TABLE)
        
        response = table.query(
            KeyConditionExpression='sessionId = :sid',
            ExpressionAttributeValues={':sid': session_id},
            ScanIndexForward=False,  # Most recent first
            Limit=limit
        )
        
        items = response.get('Items', [])
        return list(reversed(items))  # Return in chronological order
        
    except Exception as e:
        print(f"Error retrieving history: {e}")
        return []

def lambda_handler(event, context):
    """
    Main Lambda handler for chat requests
    
    Expected event:
    {
        "action": "chat",
        "sessionId": "session-123",
        "query": "What are the latest trends in AI?",
        "includeHistory": true
    }
    """
    
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse request
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event
        
        action = body.get('action', 'chat')
        session_id = body.get('sessionId', f"session-{int(datetime.now().timestamp())}")
        query = body.get('query', '')
        include_history = body.get('includeHistory', False)
        
        # Handle different actions
        if action == 'history':
            history = get_chat_history(session_id)
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'history': history
                })
            }
        
        # Validate query
        if not query:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Query is required'})
            }
        
        # Get conversation history if requested
        conversation_history = []
        if include_history:
            history = get_chat_history(session_id)
            conversation_history = [
                {'role': 'user', 'content': h['query']}
                for h in history
            ] + [
                {'role': 'assistant', 'content': h['response']}
                for h in history
            ]
        
        # Generate embedding for query
        print("Generating query embedding...")
        query_embedding = generate_embedding(query)
        
        # Search for similar articles
        print("Searching for similar articles...")
        context_articles = search_similar_articles(query_embedding)
        
        if not context_articles:
            return {
                'statusCode': 200,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'response': "I don't have any relevant articles to answer your question. Please try a different query.",
                    'sources': []
                })
            }
        
        # Construct prompt and call Claude
        print("Constructing prompt and calling Claude...")
        prompt = construct_prompt(query, context_articles, conversation_history)
        claude_response = call_claude(prompt)
        
        # Save to DynamoDB
        save_to_dynamodb(session_id, query, claude_response['text'], context_articles)
        
        # Return response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'response': claude_response['text'],
                'sources': [
                    {
                        'title': a.get('title', ''),
                        'author': a.get('author', ''),
                        'link': a.get('link', ''),
                        'published': a.get('published', ''),
                        'similarity': a.get('similarity_score', 0)
                    }
                    for a in context_articles
                ],
                'sessionId': session_id,
                'usage': claude_response.get('usage', {})
            })
        }
        
    except Exception as e:
        print(f"Error processing request: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'error': str(e),
                'message': 'Internal server error'
            })
        }
