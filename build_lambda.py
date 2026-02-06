"""
Build Lambda Deployment Package (Python version)
Alternative to build_lambda.sh for cross-platform compatibility
"""

import os
import shutil
import zipfile
import subprocess
import sys

def clean_previous_builds():
    """Remove previous build artifacts"""
    print("Cleaning previous builds...")
    if os.path.exists('package'):
        shutil.rmtree('package')
    if os.path.exists('lambda_deployment.zip'):
        os.remove('lambda_deployment.zip')

def install_dependencies():
    """Install Python dependencies"""
    print("\nInstalling dependencies...")
    os.makedirs('package', exist_ok=True)
    
    # Step 1: Install feedparser with platform restrictions
    print("Installing feedparser...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install',
        '--platform', 'manylinux2014_x86_64',
        '--target', 'package',
        '--implementation', 'cp',
        '--python-version', '3.12',
        '--only-binary=:all:',
        '--no-deps', 
        '--upgrade',
        'feedparser==6.0.11'
    ])

    # Step 2: Install sgmllib3k without platform restrictions
    # This allows pip to use the source distribution (.tar.gz)
    print("Installing sgmllib3k...")
    subprocess.check_call([
        sys.executable, '-m', 'pip', 'install',
        '--target', 'package',
        '--upgrade',
        'sgmllib3k==1.0.0'
    ])

def copy_lambda_function():
    """Copy Lambda function and config files to package"""
    print("\nCopying Lambda files...")
    # List all local files required by your Lambda
    files_to_include = [
        'lambda_function.py',
        'medium_feeds_config.py'
    ]
    
    for file in files_to_include:
        if os.path.exists(file):
            shutil.copy(file, 'package/')
            print(f"✓ Included {file}")

def create_zip():
    """Create deployment zip file"""
    print("\nCreating deployment package...")
    
    with zipfile.ZipFile('lambda_deployment.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('package'):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, 'package')
                zipf.write(file_path, arcname)
    
    size = os.path.getsize('lambda_deployment.zip')
    print(f"\n✓ Package created: lambda_deployment.zip ({size / 1024 / 1024:.2f} MB)")

def main():
    print("=" * 60)
    print("Building Lambda Deployment Package")
    print("=" * 60)
    
    try:
        clean_previous_builds()
        install_dependencies()
        copy_lambda_function()
        create_zip()
        
        print("\n" + "=" * 60)
        print("✓ Deployment package ready!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Upload lambda_deployment.zip to AWS Lambda")
        print("2. Set environment variables (see LAMBDA_DEPLOYMENT_GUIDE.md)")
        print("3. Configure EventBridge trigger")
        print()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()