#!/usr/bin/env python3

import os
import glob
import json
import argparse
from datetime import datetime

def create_summary(results_dir, total_repos, workflow_run_id=None, workflow_run_number=None):
    print(f"📊 Creating summary from results in: {results_dir}")
    print(f"📊 Workflow Run ID: {workflow_run_id}")
    print(f"📊 Workflow Run Number: {workflow_run_number}")
    
    all_prs = []
    all_failures = []
    successful_repos = set()
    
    pr_json_files = glob.glob(os.path.join(results_dir, "*-prs.json"))
    print(f"Found {len(pr_json_files)} PR JSON result files")
    
    for pr_file in pr_json_files:
        print(f"  Processing: {pr_file}")
        try:
            with open(pr_file, 'r') as f:
                batch_prs = json.load(f)
                all_prs.extend(batch_prs)
                for pr in batch_prs:
                    successful_repos.add(pr['repo'])
        except Exception as e:
            print(f"  ⚠️ Error processing {pr_file}: {str(e)}")
    
    if not all_prs:
        pr_csv_files = glob.glob(os.path.join(results_dir, "*-prs.csv"))
        print(f"Fallback: Found {len(pr_csv_files)} PR CSV result files")
        
        for pr_file in pr_csv_files:
            print(f"  Processing: {pr_file}")
            with open(pr_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('repo,'):
                        parts = line.split(',')
                        if len(parts) >= 5:
                            pr_info = {
                                'repo': parts[0],
                                'pr_number': int(parts[1]),
                                'pr_url': parts[2],
                                'head_branch': parts[3],
                                'base_branch': parts[4],
                                'created_at': parts[5] if len(parts) > 5 else '',
                                'workflow_run_id': parts[6] if len(parts) > 6 else workflow_run_id,
                                'workflow_run_number': parts[7] if len(parts) > 7 else workflow_run_number,
                                'merge_command': parts[8] if len(parts) > 8 else f"gh pr merge {parts[1]} --repo {parts[0]} --merge",
                                'squash_command': parts[9] if len(parts) > 9 else f"gh pr merge {parts[1]} --repo {parts[0]} --squash",
                                'rebase_command': parts[10] if len(parts) > 10 else f"gh pr merge {parts[1]} --repo {parts[0]} --rebase"
                            }
                            all_prs.append(pr_info)
                            successful_repos.add(parts[0])
    
    failure_files = glob.glob(os.path.join(results_dir, "*-failures.txt"))
    print(f"Found {len(failure_files)} failure result files")
    
    for failure_file in failure_files:
        print(f"  Processing: {failure_file}")
        with open(failure_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    all_failures.append(line)
    
    successful_count = len(successful_repos)
    failed_repos = set()
    for failure in all_failures:
        if failure:
            repo = failure.split(',')[0]
            failed_repos.add(repo)
    
    failed_count = len(failed_repos)
    total_repos_int = int(total_repos)
    
    os.makedirs('output', exist_ok=True)
    
    with open('output/deployment-summary.txt', 'w') as f:
        f.write("ULTRATAX WORKFLOW DEPLOYMENT SUMMARY\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Workflow Run ID: {workflow_run_id}\n")
        f.write(f"Workflow Run Number: {workflow_run_number}\n")
        f.write(f"Total Repositories: {total_repos}\n")
        f.write(f"Successful Deployments: {successful_count}\n")
        f.write(f"Failed Deployments: {failed_count}\n")
        f.write(f"Success Rate: {(successful_count/total_repos_int*100):.1f}%\n")
        f.write(f"Total PRs Created: {len(all_prs)}\n\n")
        
        if workflow_run_id and workflow_run_number:
            f.write("ARTIFACT INFORMATION:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Main Artifact: ultratax-prs-run-{workflow_run_number}-{workflow_run_id}\n")
            f.write(f"Merge Scripts: ultratax-merge-ready-run-{workflow_run_number}\n")
            f.write(f"Summary Artifact: deployment-summary-run-{workflow_run_number}\n\n")
        
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
    
    if all_prs:
        for pr in all_prs:
            if 'workflow_run_id' not in pr or not pr['workflow_run_id']:
                pr['workflow_run_id'] = workflow_run_id
            if 'workflow_run_number' not in pr or not pr['workflow_run_number']:
                pr['workflow_run_number'] = workflow_run_number
        
        with open('output/all-prs.json', 'w') as f:
            json.dump(all_prs, f, indent=2)
        
        with open('output/merge-all-prs.sh', 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Master Auto-Merge Script for All PRs\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Workflow Run ID: {workflow_run_id}\n")
            f.write(f"# Workflow Run Number: {workflow_run_number}\n")
            f.write(f"# Total PRs: {len(all_prs)}\n\n")
            
            f.write("set -e\n\n")
            
            f.write("echo \"🚀 Starting auto-merge of all PRs...\"\n")
            f.write(f"echo \"📊 Workflow Run ID: {workflow_run_id}\"\n")
            f.write(f"echo \"📊 Total PRs to merge: {len(all_prs)}\"\n\n")
            
            f.write("merge_pr() {\n")
            f.write("    local repo=$1\n")
            f.write("    local pr_number=$2\n")
            f.write("    local merge_type=${3:-merge}\n")
            f.write("    \n")
            f.write("    echo \"🔄 Merging PR #$pr_number in $repo...\"\n")
            f.write("    if gh pr merge $pr_number --repo $repo --$merge_type; then\n")
            f.write("        echo \"✅ Successfully merged PR #$pr_number in $repo\"\n")
            f.write("    else\n")
            f.write("        echo \"❌ Failed to merge PR #$pr_number in $repo\"\n")
            f.write("        echo \"$repo,$pr_number,merge_failed\" >> failed-merges.txt\n")
            f.write("    fi\n")
            f.write("    sleep 2\n")
            f.write("}\n\n")
            
            f.write("echo \"# Failed merges log\" > failed-merges.txt\n")
            f.write("echo \"# Format: repo,pr_number,error\" >> failed-merges.txt\n\n")
            
            for i, pr in enumerate(all_prs, 1):
                f.write(f"echo \"[{i}/{len(all_prs)}] Processing {pr['repo']} PR #{pr['pr_number']}\"\n")
                f.write(f"merge_pr \"{pr['repo']}\" \"{pr['pr_number']}\" \"merge\"\n")
            
            f.write("\necho \"🎉 Auto-merge completed!\"\n")
            f.write("echo \"📄 Check failed-merges.txt for any failures\"\n")
            f.write(f"echo \"📊 Workflow Run ID: {workflow_run_id}\"\n")
        
        with open('output/squash-merge-all-prs.sh', 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Squash Merge Script for All PRs\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Workflow Run ID: {workflow_run_id}\n\n")
            
            f.write("set -e\n\n")
            for pr in all_prs:
                f.write(f"echo \"🔄 Squash merging {pr['repo']} PR #{pr['pr_number']}\"\n")
                f.write(f"gh pr merge {pr['pr_number']} --repo {pr['repo']} --squash\n")
                f.write("sleep 2\n")
        
        with open('output/selective-merge.sh', 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Selective PR Merge Script\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Workflow Run ID: {workflow_run_id}\n\n")
            
            f.write("# Uncomment the PRs you want to merge:\n\n")
            for pr in all_prs:
                f.write(f"# {pr['repo']} - PR #{pr['pr_number']}\n")
                f.write(f"# gh pr merge {pr['pr_number']} --repo {pr['repo']} --merge\n\n")
        
        os.chmod('output/merge-all-prs.sh', 0o755)
        os.chmod('output/squash-merge-all-prs.sh', 0o755)
        os.chmod('output/selective-merge.sh', 0o755)
        
        with open('output/check-pr-status.sh', 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# PR Status Checker Script\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Workflow Run ID: {workflow_run_id}\n\n")
            
            f.write("echo \"📊 Checking status of all PRs...\"\n")
            f.write("echo \"Repo,PR,Status,Mergeable,URL\" > pr-status.csv\n\n")
            
            for pr in all_prs:
                f.write(f"echo \"Checking {pr['repo']} PR #{pr['pr_number']}\"\n")
                f.write(f"gh pr view {pr['pr_number']} --repo {pr['repo']} --json state,mergeable,url | jq -r '\"{pr['repo']},{pr['pr_number']},\" + .state + \",\" + (.mergeable | tostring) + \",\" + .url' >> pr-status.csv\n")
        
        os.chmod('output/check-pr-status.sh', 0o755)
        
        with open('output/pr-list-detailed.txt', 'w') as f:
            f.write("DETAILED PULL REQUEST LIST\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Workflow Run ID: {workflow_run_id}\n")
            f.write(f"Workflow Run Number: {workflow_run_number}\n")
            f.write(f"Total PRs: {len(all_prs)}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("ARTIFACT NAMES FOR AUTO-MERGE:\n")
            f.write("-" * 30 + "\n")
            if workflow_run_id and workflow_run_number:
                f.write(f"Main Artifact: ultratax-prs-run-{workflow_run_number}-{workflow_run_id}\n")
                f.write(f"Merge Scripts: ultratax-merge-ready-run-{workflow_run_number}\n")
            f.write("\n")
            
            for i, pr in enumerate(all_prs, 1):
                f.write(f"{i}. {pr['repo']}\n")
                f.write(f"   PR Number: #{pr['pr_number']}\n")
                f.write(f"   URL: {pr['pr_url']}\n")
                f.write(f"   Branches: {pr['head_branch']} → {pr['base_branch']}\n")
                f.write(f"   Created: {pr.get('created_at', 'N/A')}\n")
                f.write(f"   Workflow Run: {pr.get('workflow_run_id', 'N/A')}\n")
                f.write(f"   Merge Command: {pr['merge_command']}\n")
                f.write("-" * 50 + "\n")
    
    if all_failures:
        with open('output/failed-deployments.txt', 'w') as f:
            f.write("FAILED DEPLOYMENT DETAILS\n")
            f.write("=" * 30 + "\n\n")
            f.write(f"Workflow Run ID: {workflow_run_id}\n")
            f.write("Format: repo,branch,error\n\n")
            
            for failure in all_failures:
                f.write(f"{failure}\n")
    
    with open('output/summary.md', 'w') as f:
        f.write(f"### 📊 UltraTax Workflow Deployment Results\n\n")
        f.write(f"- **Total Repositories:** {total_repos}\n")
        f.write(f"- **Successful Deployments:** {successful_count} ({(successful_count/total_repos_int*100):.1f}%)\n")
        f.write(f"- **Failed Deployments:** {failed_count} ({(failed_count/total_repos_int*100):.1f}%)\n")
        f.write(f"- **Pull Requests Created:** {len(all_prs)}\n\n")
        
        if workflow_run_id and workflow_run_number:
            f.write(f"### 🎯 Artifact Information\n\n")
            f.write(f"- **Workflow Run ID:** `{workflow_run_id}`\n")
            f.write(f"- **Main PR Artifact:** `ultratax-prs-run-{workflow_run_number}-{workflow_run_id}`\n")
            f.write(f"- **Merge Scripts:** `ultratax-merge-ready-run-{workflow_run_number}`\n\n")
        
        if all_prs:
            f.write(f"### 🔀 Auto-Merge Options\n\n")
            f.write(f"**Using Auto-Merge Workflow:**\n")
            f.write(f"1. Go to **Actions** → **Auto-Merge Deployment PRs**\n")
            f.write(f"2. Use artifact: `ultratax-prs-run-{workflow_run_number}-{workflow_run_id}`\n")
            f.write(f"3. Use run ID: `{workflow_run_id}`\n\n")
            
            f.write(f"**Using Scripts:**\n")
            f.write(f"```bash\n")
            f.write(f"# Merge all PRs\n")
            f.write(f"bash output/merge-all-prs.sh\n\n")
            f.write(f"# Squash merge all PRs\n")
            f.write(f"bash output/squash-merge-all-prs.sh\n\n")

            f.write(f"# Check PR status first\n")
            f.write(f"bash output/check-pr-status.sh\n")
            f.write(f"```\n\n")
            
            f.write(f"### 📋 Created Pull Requests\n\n")
            for i, pr in enumerate(all_prs[:10], 1):
                f.write(f"{i}. **{pr['repo']}**: [PR #{pr['pr_number']}]({pr['pr_url']}) ({pr['head_branch']} → {pr['base_branch']})\n")
            
            if len(all_prs) > 10:
                f.write(f"\n... and {len(all_prs) - 10} more PRs\n")
            f.write(f"\n")
        
        if all_failures:
            f.write(f"### ⚠️ Failed Deployments\n\n")
            f.write(f"See `failed-deployments.txt` for detailed error information.\n\n")
        
        f.write(f"### 📋 Next Steps\n\n")
        f.write(f"1. **Review PRs**: Check the created pull requests\n")
        f.write(f"2. **Auto-merge**: Use the Auto-Merge workflow or provided scripts\n")
        f.write(f"3. **Monitor**: Check for any merge conflicts or failures\n")
        if all_failures:
            f.write(f"4. **Fix Issues**: Address failed deployments\n")
    
    print(f"\n🎉 Summary created successfully!")
    print(f"📊 Results: {successful_count}/{total_repos} repositories processed successfully")
    print(f"🔀 Pull requests created: {len(all_prs)}")
    if all_failures:
        print(f"⚠️ Failures recorded: {len(all_failures)}")
    print(f"📁 Summary files saved to output/ directory")
    
    if all_prs and workflow_run_id and workflow_run_number:
        print(f"\n💡 Auto-merge artifact information:")
        print(f"   • Main artifact: ultratax-prs-run-{workflow_run_number}-{workflow_run_id}")
        print(f"   • Workflow run ID: {workflow_run_id}")
        print(f"   • Use Auto-Merge Deployment PRs workflow")

def main():
    parser = argparse.ArgumentParser(description='Create deployment summary from batch results')
    parser.add_argument('--results-dir', required=True, help='Directory containing batch result files')
    parser.add_argument('--total-repos', required=True, help='Total number of repositories')
    parser.add_argument('--workflow-run-id', help='GitHub workflow run ID')
    parser.add_argument('--workflow-run-number', help='GitHub workflow run number')
    
    args = parser.parse_args()
    
    create_summary(args.results_dir, args.total_repos, args.workflow_run_id, args.workflow_run_number)

if __name__ == "__main__":
    main()