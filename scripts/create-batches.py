#!/usr/bin/env python3

import json
import argparse
import os

def create_batches(repos_file, batch_size):
    """Create repository batches for parallel processing"""
    
    # Load repositories from file
    repos = []
    try:
        with open(repos_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    repos.append(line)
        
        print(f"✅ Loaded {len(repos)} repositories from {repos_file}")
        
    except FileNotFoundError:
        print(f"❌ Repository file not found: {repos_file}")
        exit(1)
    
    if not repos:
        print("❌ No repositories found in the file")
        exit(1)
    
    # Create batches
    batches = []
    for i in range(0, len(repos), batch_size):
        batch_repos = repos[i:i + batch_size]
        batches.append({
            'id': i // batch_size,
            'repositories': batch_repos,
            'size': len(batch_repos)
        })
    
    print(f"✅ Created {len(batches)} batches with max {batch_size} repos each")
    
    # Save batch configuration
    config = {
        'batches': batches,
        'total_repositories': len(repos),
        'batch_size': batch_size
    }
    
    with open('batch-config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    # Output for GitHub Actions
    batch_ids = [str(b['id']) for b in batches]
    
    # Set GitHub Actions outputs
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"batches={json.dumps(batch_ids)}\n")
            f.write(f"total_repos={len(repos)}\n")
    
    print(f"Batch IDs: {batch_ids}")
    print(f"Total repositories: {len(repos)}")

def main():
    parser = argparse.ArgumentParser(description='Create repository batches for parallel processing')
    parser.add_argument('--repos-file', required=True, help='Repository list file')
    parser.add_argument('--batch-size', type=int, default=15, help='Number of repositories per batch')
    
    args = parser.parse_args()
    create_batches(args.repos_file, args.batch_size)

if __name__ == "__main__":
    main()