#!/usr/bin/env python3

import os
import json
import yaml
import argparse
import time
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from github import Github, Auth

class SimpleWorkflowDeployer:
    def __init__(self, github_token, batch_id, workflow_run_id=None, workflow_run_number=None):
        auth = Auth.Token(github_token)
        self.github = Github(auth=auth)
        self.batch_id = batch_id
        self.workflow_run_id = workflow_run_id
        self.workflow_run_number = workflow_run_number
        self.results = {
            'successful': [],
            'failed': [],
            'prs_created': [],
            'skipped': []
        }
        
        self.jinja_env = Environment(
            loader=FileSystemLoader('templates'),
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}',
            comment_start_string='{#',
            comment_end_string='#}'
        )
        
        try:
            self.template = self.jinja_env.get_template('ultratax-workflow.yml.j2')
            print(f"✅ Template loaded successfully")
        except Exception as e:
            print(f"❌ Error loading template: {str(e)}")
            raise e
    
    def load_repo_values(self):
        config_file = 'config/repo-values.yaml'
        if not os.path.exists(config_file):
            print(f"❌ Config file not found: {config_file}")
            print("💡 Creating default config file...")
            self.create_default_config()
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                print(f"✅ Configuration loaded from {config_file}")
                return config
        except Exception as e:
            print(f"❌ Error loading config: {str(e)}")
            exit(1)
    
    def create_default_config(self):
        os.makedirs('config', exist_ok=True)
        
        default_config = {
            'default': {
                'publication_targets': 'STest',
                'solution_files': 'src/solution.sln',
                'packable_nuspec_files': '',
                'nuget_config_file': ''
            }
        }
        
        with open('config/repo-values.yaml', 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        print("✅ Created default config/repo-values.yaml")
    
    def load_batch_repos(self):
        batch_file = 'batch-config.json'
        
        if not os.path.exists(batch_file):
            print(f"❌ Batch config file not found: {batch_file}")
            print("💡 Creating batch config from repos.txt...")
            self.create_batch_config()
        
        try:
            with open(batch_file, 'r') as f:
                config = json.load(f)
            
            for batch in config['batches']:
                if batch['id'] == self.batch_id:
                    print(f"✅ Found batch {self.batch_id} with {len(batch['repositories'])} repositories")
                    return batch['repositories']
            
            print(f"❌ Batch {self.batch_id} not found in configuration")
            return []
            
        except Exception as e:
            print(f"❌ Error loading batch config: {str(e)}")
            return []
    
    def create_batch_config(self):
        repos_file = 'repos.txt'
        
        if not os.path.exists(repos_file):
            print(f"❌ Repository file not found: {repos_file}")
            print("💡 Creating default repos.txt...")
            with open(repos_file, 'w') as f:
                f.write("# Add
 your repositories here (format: org/repo-name)\n")
                f.write("# Example:\n")
                f.write("# your-org/test-repo-1\n")
                f.write("# your-org/test-repo-2\n")
            print("✅ Created default repos.txt - please add your repositories")
            exit(1)
        
        repos = []
        with open(repos_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    repos.append(line)
        
        if not repos:
            print("❌ No repositories found in repos.txt")
            exit(1)
        
        batch_config = {
            "batches": [
                {
                    "id": 0,
                    "repositories": repos,
                    "size": len(repos)
                }
            ],
            "total_repositories": len(repos),
            "batch_size": len(repos),
            "batch_count": 1
        }
        
        with open('batch-config.json', 'w') as f:
            json.dump(batch_config, f, indent=2)
        
        print(f"✅ Created batch-config.json with {len(repos)} repositories")
    
    def get_repo_config(self, repo_name, repo_values):
        repo_short = repo_name.split('/')[-1]
        
        if repo_short in repo_values:
            config = repo_values[repo_short].copy()
            print(f"    📋 Using specific config for {repo_short}")
        else:
            config = repo_values['default'].copy()
            print(f"    📋 Using default config for {repo_short}")
        
        return config
    
    def render_workflow(self, repo_config):
        try:
            return self.template.render(**repo_config)
        except Exception as e:
            print(f"    ❌ Template rendering failed: {str(e)}")
            return None
    
    def deploy_to_repo(self, repo_name, branches, file_location, create_prs, dry_run):
        print(f"  🔄 Processing: {repo_name}")
        
        try:
            repo_values = self.load_repo_values()
            repo_config = self.get_repo_config(repo_name, repo_values)
            
            workflow_content = self.render_workflow(repo_config)
            if not workflow_content:
                self.results['failed'].append({
                    'repo': repo_name,
                    'error': 'Template rendering failed'
                })
                return
            
            if dry_run:
                print(f"    🔍 DRY RUN: Would create workflow with config:")
                print(f"      - Publication Targets: {repo_config['publication_targets']}")
                print(f"      - Solution Files: {repo_config['solution_files']}")
                print(f"      - Packable Nuspec Files: {repo_config['packable_nuspec_files']}")
                self.results['successful'].append(repo_name)
                return
            
            github_repo = self.github.get_repo(repo_name)
            
            branch_success = False
            for branch in branches:
                try:
                    github_repo.get_branch(branch)
                    print(f"    ✅ Branch '{branch}' exists")
                    
                    if create_prs:
                        timestamp = int(datetime.now().timestamp())
                        feature_branch = f"ultratax-workflow-{timestamp}-{branch}"
                        base_branch = github_repo.get_branch(branch)
                        
                        try:
                            github_repo.create_git_ref(
                                ref=f"refs/heads/{feature_branch}",
                                sha=base_branch.commit.sha
                            )
                            print(f"    ✅ Created feature branch: {feature_branch}")
                            target_branch = feature_branch
                        except Exception as e:
                            if "Reference already exists" in str(e):
                                print(f"    ⚠️ Feature branch already exists, using existing one")
                                target_branch = feature_branch
                            else:
                                raise e
                    else:
                        target_branch = branch
                    
                    self.create_workflow_file(
                        github_repo, 
                        file_location, 
                        workflow_content, 
                        target_branch
                    )
                    
                    if create_prs:
                        pr = self.create_pull_request(
                            github_repo,
                            repo_name,
                            feature_branch,
                            branch,
                            file_location,
                            repo_config
                        )
                        if pr:
                            pr_info = {
                                'repo': repo_name,
                                'repo_owner': repo_name.split('/')[0],
                                'repo_name': repo_name.split('/')[1],
                                'pr_number': pr.number,
                                'pr_url': pr.html_url,
                                'head_branch': feature_branch,
                                'base_branch': branch,
                                'file_location': file_location,
                                'created_at': datetime.now().isoformat(),
                                'batch_id': self.batch_id,
                                'workflow_run_id': self.workflow_run_id,
                                'workflow_run_number': self.workflow_run_number,
                                'status': 'open',
                                'mergeable': None,
                                'merge_command': f"gh pr merge {pr.number} --repo {repo_name} --merge",
                                'squash_command': f"gh pr merge {pr.number} --repo {repo_name} --squash",
                                'rebase_command': f"gh pr merge {pr.number} --repo {repo_name} --rebase"
                            }
                            self.results['prs_created'].append(pr_info)
                    
                    print(f"    ✅ Success for branch: {branch}")
                    branch_success = True
                    
                except Exception as e:
                    print(f"    ❌ Error with branch {branch}: {str(e)}")
                    self.results['failed'].append({
                        'repo': repo_name,
                        'branch': branch,
                        'error': str(e)
                    })
            
            if branch_success:
                self.results['successful'].append(repo_name)
            
        except Exception as e:
            print(f"    ❌ Repository error: {str(e)}")
            self.results['failed'].append({
                'repo': repo_name,
                'error': str(e)
            })
    
    def create_workflow_file(self, github_repo, file_path, content, branch):
        try:
            try:
                existing_file = github_repo.get_contents(file_path, ref=branch)
                github_repo.update_file(
                    path=file_path,
                    message="Update UltraTax workflow configuration",
                    content=content,
                    sha=existing_file.sha,
                    branch=branch
                )
                print(f"      ✅ Updated existing file: {file_path}")
            except:
                github_repo.create_file(
                    path=file_path,
                    message="Add UltraTax workflow configuration",
                    content=content,
                    branch=branch
                )
                print(f"      ✅ Created new file: {file_path}")
                
        except Exception as e:
            print(f"      ❌ File operation failed: {str(e)}")
            raise e
    
    def create_pull_request(self, github_repo, repo_name, head_branch, base_branch, file_path, repo_config):
        try:
            pr_title = "Add/Update UltraTax Build and Deploy Workflow"
            
            pr_body = f"""
## 🚀 UltraTax Workflow Deployment

This PR adds/updates the UltraTax build and deploy workflow configuration.

### 📋 Configuration Applied:
- **Publication Targets**: `{repo_config['publication_targets']}`
- **Solution Files**: `{repo_config['solution_files']}`
- **Packable Nuspec Files**: `{repo_config['packable_nuspec_files']}`
{f"- **NuGet Config File**: `{repo_config['nuget_config_file']}`" if repo_config.get('nuget_config_file') else "- **NuGet Config File**: Using default"}

### 📁 Changes:
- Added/Updated: `{file_path}`

### 🔧 Workflow Features:
- ✅ Manual dispatch with validation options
- ✅ Automatic builds on dev and release branches
- ✅ Pull request validation
- ✅ Code signing support (Test/Production)
- ✅ Configurable publication targets

### 🤖 Auto-generated Information:
- **Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Batch ID**: {self.batch_id}
- **Workflow Run ID**: {self.workflow_run_id}
- **Workflow Run Number**: {self.workflow_run_number}
- **Repository**: {repo_name}

### 🔀 Auto-merge Information:
For bulk auto-merge, use:
- **Workflow**: Auto-Merge Deployment PRs
- **Artifact**: ultratax-prs-run-{self.workflow_run_number}-{self.workflow_run_id}
- **Run ID**: {self.workflow_run_id}

---
*
This PR was automatically created by the UltraTax Workflow Deployer*
            """
            
            pr = github_repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=head_branch,
                base=base_branch
            )
            
            print(f"      ✅ Created PR #{pr.number}: {pr.html_url}")
            return pr
            
        except Exception as e:
            print(f"      ❌ PR creation failed: {str(e)}")
            return None
    
    def save_results(self):
        os.makedirs('output', exist_ok=True)
        
        with open(f'output/batch-{self.batch_id}-summary.txt', 'w') as f:
            f.write(f"Batch {self.batch_id} Processing Results\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Workflow Run ID: {self.workflow_run_id}\n")
            f.write(f"Workflow Run Number: {self.workflow_run_number}\n")
            f.write(f"Batch ID: {self.batch_id}\n")
            f.write(f"Successful Deployments: {len(self.results['successful'])}\n")
            f.write(f"Failed Deployments: {len(self.results['failed'])}\n")
            f.write(f"Pull Requests Created: {len(self.results['prs_created'])}\n\n")
            
            if self.results['successful']:
                f.write("SUCCESSFUL REPOSITORIES:\n")
                f.write("-" * 25 + "\n")
                for repo in self.results['successful']:
                    f.write(f"✅ {repo}\n")
                f.write("\n")
            
            if self.results['failed']:
                f.write("FAILED REPOSITORIES:\n")
                f.write("-" * 20 + "\n")
                for failure in self.results['failed']:
                    f.write(f"❌ {failure['repo']}: {failure['error']}\n")
        
        if self.results['prs_created']:
            with open(f'output/batch-{self.batch_id}-prs.json', 'w') as f:
                json.dump(self.results['prs_created'], f, indent=2)
            
            with open(f'output/batch-{self.batch_id}-prs.csv', 'w') as f:
                f.write("repo,pr_number,pr_url,head_branch,base_branch,created_at,workflow_run_id,workflow_run_number,merge_command,squash_command,rebase_command\n")
                for pr in self.results['prs_created']:
                    f.write(f"{pr['repo']},{pr['pr_number']},{pr['pr_url']},{pr['head_branch']},{pr['base_branch']},{pr['created_at']},{pr['workflow_run_id']},{pr['workflow_run_number']},{pr['merge_command']},{pr['squash_command']},{pr['rebase_command']}\n")
            
            with open(f'output/batch-{self.batch_id}-merge-commands.sh', 'w') as f:
                f.write("#!/bin/bash\n")
                f.write(f"# Auto-merge commands for Batch {self.batch_id}\n")
                f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Workflow Run ID: {self.workflow_run_id}\n")
                f.write(f"# Workflow Run Number: {self.workflow_run_number}\n\n")
                f.write("# Merge with merge commit (preserves commit history)\n")
                for pr in self.results['prs_created']:
                    f.write(f"{pr['merge_command']}\n")
                f.write("\n# Alternative: Squash and merge (single commit)\n")
                for pr in self.results['prs_created']:
                    f.write(f"# {pr['squash_command']}\n")
                f.write("\n# Alternative: Rebase and merge (linear history)\n")
                for pr in self.results['prs_created']:
                    f.write(f"# {pr['rebase_command']}\n")
            
            os.chmod(f'output/batch-{self.batch_id}-merge-commands.sh', 0o755)
        
        if self.results['failed']:
            with open(f'output/batch-{self.batch_id}-failures.txt', 'w') as f:
                f.write("# Format: repo,branch,error\n")
                for failure in self.results['failed']:
                    branch = failure.get('branch', 'N/A')
                    error = failure['error'].replace(',', ';')
                    f.write(f"{failure['repo']},{branch},{error}\n")
        
        print(f"✅ Batch {self.batch_id} results saved to output/ directory")
        if self.results['prs_created']:
            print(f"🔀 PR merge commands saved to: output/batch-{self.batch_id}-merge-commands.sh")
    
    def deploy_batch(self, branches_input, file_location, create_prs, dry_run):
        repositories = self.load_batch_repos()
        if not repositories:
            print(f"❌ No repositories found for batch {self.batch_id}")
            return
        
        branches = [b.strip() for b in branches_input.split(',') if b.strip()]
        
        print(f"🚀 Starting Batch {self.batch_id} Deployment")
        print(f"📊 Workflow Run ID: {self.workflow_run_id}")
        print(f"📊 Workflow Run Number: {self.workflow_run_number}")
        print(f"📦 Repositories in batch: {len(repositories)}")
        print(f"🎯 Target branches: {', '.join(branches)}")
        print(f"📁 File location: {file_location}")
        print(f"🔍 Dry run mode: {dry_run}")
        print(f"🔀 Create PRs: {create_prs}")
        print("-" * 50)
        
        for repo_name in repositories:
            self.deploy_to_repo(repo_name, branches, file_location, create_prs, dry_run)
            time.sleep(1)
        
        self.save_results()
        
        print(f"\n🎉 Batch {self.batch_id} completed!")
        print(f"✅ Successful: {len(self.results['successful'])}")
        print(f"❌ Failed: {len(self.results['failed'])}")
        print(f"🔀 PRs created: {len(self.results['prs_created'])}")
        
        if self.results['prs_created']:
            print(f"\n📋 Pull Requests Created:")
            for pr in self.results['prs_created']:
                print(f"  • {pr['repo']} - PR #{pr['pr_number']}: {pr['pr_url']}")
            print(f"\n💡 To auto-merge all PRs, run:")
            print(f"   bash output/batch-{self.batch_id}-merge-commands.sh")
            print(f"\n🔀 Or use the Auto-Merge workflow with:")
            print(f"   • Workflow Run ID: {self.workflow_run_id}")
            print(f"   • Artifact Name: ultratax-prs-run-{self.workflow_run_number}-{self.workflow_run_id}")

def main():
    parser = argparse.ArgumentParser(description='Deploy UltraTax workflows to a batch of repositories')
    parser.add_argument('--token', required=True, help='GitHub personal access token')
    parser.add_argument('--batch-id', type=int, required=True, help='Batch ID to process')
    parser.add_argument('--branches', required=True, help='Comma-separated list of target branches')
    parser.add_argument('--file-location', required=True, help='Target file location in repositories')
    parser.add_argument('--create-prs', default='true', help='Create pull requests (true/false)')
    parser.add_argument('--dry-run', default='false', help='Dry run mode (true/false)')
    parser.add_argument('--workflow-run-id', help='GitHub workflow run ID')
    parser.add_argument('--workflow-run-number', help='GitHub workflow run number')
    
    args = parser.parse_args()
    
    create_prs = args.create_prs.lower() == 'true'
    dry_run = args.dry_run.lower() == 'true'
    
    deployer = SimpleWorkflowDeployer(
        args.token, 
        args.batch_id, 
        args.workflow_run_id, 
        args.workflow_run_number
    )
    deployer.deploy_batch(args.branches, args.file_location, create_prs, dry_run)

if __name__ == "__main__":
    main()