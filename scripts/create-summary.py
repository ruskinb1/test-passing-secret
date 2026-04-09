#!/usr/bin/env python3

import os
import glob
import argparse
from datetime import datetime

def create_summary(results_dir, total_repos):
    """Create a comprehensive summary from all batch results"""
    
    print(f"📊 Creating summary from results in: {results_dir}")
    
    # Collect all results
    all_prs = []
    all_failures = []
    successful_repos = set()
    
    # Process PR files
    pr_files = glob.glob(os.path.join(results_dir, "*-prs.txt"))
    print(f"Found {len(pr_files)} PR result files")
    
    for pr_file in pr_files:
        print(f"  Processing: {pr_file}")
        with open(pr_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    all_prs.append(line)
                    # Extract repo name (first part before comma)
                    repo = line.split(',')[0]

                    successful_repos.add(repo)
    
    # Process failure files
    failure_files = glob.glob(os.path.join(results_dir, "*-failures.txt"))
    print(f"Found {len(failure_files)} failure result files")
    
    for failure_file in failure_files:
        print(f"  Processing: {failure_file}")
        with open(failure_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    all_failures.append(line)
    
    # Calculate statistics
    successful_count = len(successful_repos)
    failed_repos = set()
    for failure in all_failures:
        if failure:
            repo = failure.split(',')[0]
            failed_repos.add(repo)
    
    failed_count = len(failed_repos)
    total_repos_int = int(total_repos)
    
    # Create output directory
    os.makedirs('output', exist_ok=True)
    
    # Create main deployment summary
    with open('output/deployment-summary.txt', 'w') as f:
        f.write("ULTRATAX WORKFLOW DEPLOYMENT SUMMARY\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Repositories: {total_repos}\n")
        f.write(f"Successful Deployments: {successful_count}\n")
        f.write(f"Failed Deployments: {failed_count}\n")
        f.write(f"Success Rate: {(successful_count/total_repos_int*100):.1f}%\n")
        f.write(f"Total PRs Created: {len(all_prs)}\n\n")
        
        if successful_repos:
            f.write("SUCCESSFUL REPOSITORIES:\n")
            f.write("-" * 25 + "\n")
            for repo in sorted(successful_repos):
                f.write(f"✅ {repo}\n")
            f.write("\n")
        
        if failed_repos:
            f.write("FAILED REPOSITORIES:\n")
            f.write("-" * 20 + "\n")
            for repo in sorted(failed_repos):
                f.write(f"❌ {repo}\n")
    
    # Create complete PR list with merge commands
    if all_prs:
        with open('output/pr-list-complete.txt', 'w') as f:
            f.write("COMPLETE PULL REQUEST LIST\n")
            f.write("=" * 30 + "\n\n")
            f.write("Format: repo,pr_number,pr_url,branch\n\n")
            
            for pr in all_prs:
                f.write(f"{pr}\n")
            
            f.write(f"\n\nGITHUB CLI MERGE COMMANDS:\n")
            f.write("-" * 30 + "\n")
            f.write("# Copy and paste these commands to merge all PRs:\n\n")
            
            for pr in all_prs:
                parts = pr.split(',')
                if len(parts) >= 2:
                    repo, pr_number = parts[0], parts[1]
                    f.write(f"gh pr merge {pr_number} --repo {repo} --merge\n")
            
            f.write(f"\n# Or to merge with squash:\n")
            for pr in all_prs:
                parts = pr.split(',')
                if len(parts) >= 2:
                    repo, pr_number = parts[0], parts[1]
                    f.write(f"gh pr merge {pr_number} --repo {repo} --squash\n")
    
    # Create failure details
    if all_failures:
        with open('output/failed-deployments.txt', 'w') as f:
            f.write("FAILED DEPLOYMENT DETAILS\n")
            f.write("=" * 30 + "\n\n")
            f.write("Format: repo,branch,error\n\n")
            
            for failure in all_failures:
                f.write(f"{failure}\n")
    
    # Create markdown summary for GitHub Actions
    with open('output/summary.md', 'w') as f:
        f.write(f"### 📊 UltraTax Workflow Deployment Results\n\n")
        f.write(f"- **Total Repositories:** {total_repos}\n")
        f.write(f"- **Successful Deployments:** {successful_count} ({(successful_count/total_repos_int*100):.1f}%)\n")
        f.write(f"- **Failed Deployments:** {failed_count} ({(failed_count/total_repos_int*100):.1f}%)\n")
        f.write(f"- **Pull Requests Created:** {len(all_prs)}\n\n")
        
        if all_prs:
            f.write(f"### 🔀 Created Pull Requests\n\n")
            for pr in all_prs[:10]:  # Show first 10 PRs
                parts = pr.split(',')
                if len(parts) >= 3:
                    repo, pr_number, pr_url = parts[0], parts[1], parts[2]
                    f.write(f"- **{repo}**: [PR #{pr_number}]({pr_url})\n")
            
            if len(all_prs) > 10:
                f.write(f"- ... and {len(all_prs) - 10} more PRs\n")
            f.write(
f"\n")
        
        if all_failures:
            f.write(f"### ⚠️ Failed Deployments\n\n")
            f.write(f"See `failed-deployments.txt` for detailed error information.\n\n")
        
        f.write(f"### 📋 Next Steps\n\n")
        f.write(f"1. Review the `pr-list-complete.txt` for all created PRs\n")
        f.write(f"2. Use the GitHub CLI commands to bulk merge PRs\n")
        if all_failures:
            f.write(f"3. Check `failed-deployments.txt` for any issues to resolve\n")
    
    # Print summary to console
    print(f"\n🎉 Summary created successfully!")
    print(f"📊 Results: {successful_count}/{total_repos} repositories processed successfully")
    print(f"🔀 Pull requests created: {len(all_prs)}")
    if all_failures:
        print(f"⚠️ Failures recorded: {len(all_failures)}")
    print(f"📁 Summary files saved to output/ directory")

def main():
    parser = argparse.ArgumentParser(description='Create deployment summary from batch results')
    parser.add_argument('--results-dir', required=True, help='Directory containing batch result files')
    parser.add_argument('--total-repos', required=True, help='Total number of repositories')
    
    args = parser.parse_args()
    
    create_summary(args.results_dir, args.total_repos)

if __name__ == "__main__":
    main()