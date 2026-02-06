"""
Auto-generated Medium RSS Feed Configuration
Generated with 84 topic feeds and 26 publication feeds
Total potential articles per run: ~1100
"""

# Topic-based RSS feeds (84 feeds)
TOPIC_FEEDS = ['https://medium.com/feed/tag/artificial-intelligence', 'https://medium.com/feed/tag/machine-learning', 'https://medium.com/feed/tag/data-science', 'https://medium.com/feed/tag/deep-learning', 'https://medium.com/feed/tag/python', 'https://medium.com/feed/tag/javascript', 'https://medium.com/feed/tag/java', 'https://medium.com/feed/tag/cpp', 'https://medium.com/feed/tag/golang', 'https://medium.com/feed/tag/rust', 'https://medium.com/feed/tag/typescript', 'https://medium.com/feed/tag/react', 'https://medium.com/feed/tag/angular', 'https://medium.com/feed/tag/vuejs', 'https://medium.com/feed/tag/nodejs', 'https://medium.com/feed/tag/django', 'https://medium.com/feed/tag/flask', 'https://medium.com/feed/tag/fastapi', 'https://medium.com/feed/tag/aws', 'https://medium.com/feed/tag/azure', 'https://medium.com/feed/tag/google-cloud', 'https://medium.com/feed/tag/docker', 'https://medium.com/feed/tag/kubernetes', 'https://medium.com/feed/tag/devops', 'https://medium.com/feed/tag/cicd', 'https://medium.com/feed/tag/blockchain', 'https://medium.com/feed/tag/cryptocurrency', 'https://medium.com/feed/tag/bitcoin', 'https://medium.com/feed/tag/ethereum', 'https://medium.com/feed/tag/web3', 'https://medium.com/feed/tag/nft', 'https://medium.com/feed/tag/cybersecurity', 'https://medium.com/feed/tag/infosec', 'https://medium.com/feed/tag/ethical-hacking', 'https://medium.com/feed/tag/penetration-testing', 'https://medium.com/feed/tag/ios-development', 'https://medium.com/feed/tag/android-development', 'https://medium.com/feed/tag/flutter', 'https://medium.com/feed/tag/react-native', 'https://medium.com/feed/tag/game-development', 'https://medium.com/feed/tag/unity', 'https://medium.com/feed/tag/unreal-engine', 'https://medium.com/feed/tag/big-data', 'https://medium.com/feed/tag/data-analytics', 'https://medium.com/feed/tag/data-visualization', 'https://medium.com/feed/tag/tableau', 'https://medium.com/feed/tag/powerbi', 'https://medium.com/feed/tag/sql', 'https://medium.com/feed/tag/mongodb', 'https://medium.com/feed/tag/postgresql', 'https://medium.com/feed/tag/redis', 'https://medium.com/feed/tag/elasticsearch', 'https://medium.com/feed/tag/apache-spark', 'https://medium.com/feed/tag/hadoop', 'https://medium.com/feed/tag/kafka', 'https://medium.com/feed/tag/airflow', 'https://medium.com/feed/tag/natural-language-processing', 'https://medium.com/feed/tag/computer-vision', 'https://medium.com/feed/tag/reinforcement-learning', 'https://medium.com/feed/tag/neural-networks', 'https://medium.com/feed/tag/transformers', 'https://medium.com/feed/tag/gpt', 'https://medium.com/feed/tag/llm', 'https://medium.com/feed/tag/chatgpt', 'https://medium.com/feed/tag/tensorflow', 'https://medium.com/feed/tag/pytorch', 'https://medium.com/feed/tag/keras', 'https://medium.com/feed/tag/scikit-learn', 'https://medium.com/feed/tag/startup', 'https://medium.com/feed/tag/entrepreneurship', 'https://medium.com/feed/tag/business-strategy', 'https://medium.com/feed/tag/product-management', 'https://medium.com/feed/tag/leadership', 'https://medium.com/feed/tag/management', 'https://medium.com/feed/tag/career', 'https://medium.com/feed/tag/career-advice', 'https://medium.com/feed/tag/job-search', 'https://medium.com/feed/tag/remote-work', 'https://medium.com/feed/tag/freelancing', 'https://medium.com/feed/tag/side-hustle', 'https://medium.com/feed/tag/passive-income', 'https://medium.com/feed/tag/productivity', 'https://medium.com/feed/tag/time-management', 'https://medium.com/feed/tag/self-improvement']

# Publication RSS feeds (26 feeds)
PUBLICATION_FEEDS = ['https://medium.com/feed/@towardsdatascience', 'https://medium.com/feed/better-programming', 'https://medium.com/feed/python-in-plain-english', 'https://medium.com/feed/javascript-in-plain-english', 'https://medium.com/feed/codex', 'https://medium.com/feed/analytics-vidhya', 'https://medium.com/feed/the-startup', 'https://medium.com/feed/hackernoon', 'https://medium.com/feed/dev-genius', 'https://medium.com/feed/level-up-coding', 'https://medium.com/feed/towards-dev', 'https://medium.com/feed/towards-ai', 'https://medium.com/feed/ai-in-plain-english', 'https://medium.com/feed/data-driven-investor', 'https://medium.com/feed/the-programming-hub', 'https://medium.com/feed/git-connected', 'https://medium.com/feed/geek-culture', 'https://medium.com/feed/aws-in-plain-english', 'https://medium.com/feed/cloud-native-daily', 'https://medium.com/feed/itnext', 'https://medium.com/feed/ux-collective', 'https://medium.com/feed/bootcamp', 'https://medium.com/feed/entrepreneur-handbook', 'https://medium.com/feed/better-humans', 'https://medium.com/feed/personal-growth', 'https://medium.com/feed/the-writing-cooperative']

# All feeds combined
ALL_FEEDS = TOPIC_FEEDS + PUBLICATION_FEEDS

# Recommended subsets for different use cases
TECH_FOCUSED = [feed for feed in TOPIC_FEEDS if any(
    keyword in feed for keyword in ['python', 'javascript', 'programming', 'ai', 'machine-learning', 'data', "artificial-intelligence", "machine-learning", "data-science", "deep-learning",
    "java", "cpp", "golang", "rust", "typescript",
    "react", "angular", "vuejs", "nodejs", "django", "flask", "fastapi",
    "aws", "azure", "google-cloud", "docker", "kubernetes", "devops", "cicd",
    "ios-development", "android-development", "flutter", "react-native",
    "game-development"]
)]

AIML_FOCUSED = [feed for feed in TOPIC_FEEDS if any(
    keyword in feed for keyword in ["big-data", "data-analytics", "data-visualization", "tableau", "powerbi",
    "sql", "mongodb", "postgresql", "redis", "elasticsearch",
    "apache-spark", "hadoop", "kafka", "airflow","natural-language-processing", "computer-vision", "reinforcement-learning",
    "neural-networks", "transformers", "gpt", "llm", "chatgpt",
    "tensorflow", "pytorch", "keras", "scikit-learn"]
)]

BUSINESS_FOCUSED = [feed for feed in TOPIC_FEEDS if any(
    keyword in feed for keyword in ['startup', 'entrepreneur', 'business', 'leadership', 'product']
)]

DESIGN_FOCUSED = [feed for feed in TOPIC_FEEDS if any(
    keyword in feed for keyword in ['design', 'ux', 'ui']
)]
