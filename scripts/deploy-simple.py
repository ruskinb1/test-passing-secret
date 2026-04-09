#!/usr/bin/env python3

import os
import json
import yaml
import argparse
import time
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from github import Github, Auth
import github

class SimpleWorkflowDeployer:
    def __init__(self, github_token, batch_id):
        # Fix: Use new PyGithub authentication method
        auth = Auth.Token(github_token)
        self.github = Github(auth=auth)
        self.batch_id = batch_id
        self.results = {
            'successful': [],
            'failed': [],
            'prs_created': []
        }
        
        # Setup Jinja2 with custom delimiters to avoid conflicts with GitHub Actions syntax
        self.jinja_env = Environment(
            loader=FileSystemLoader('templates'),
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}',
            comment_start_string='{#',
            comment_end_string='#}'
        )
        
        # Load template with error handling
        try:
            self.template = self.jinja_env.get_template('ultratax-workflow.yml.j2')
        except Exception as e:
            print(f"❌ Error loading template: {str(e)}")
            raise e
    
    def load_repo_values(self):
        """Load repository-specific values from config file"""
        try:
            with open('config/repo-values.yaml', 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print("❌ Config file not found: config/repo-values.yaml")
            exit(1)
    
    def load_batch_repos(self):
        """Load repositories for this specific batch"""
        try:
            with open('batch-config.json', 'r') as f:
                config = json.load(f)
            
            for batch in config['batches']:
                if batch['id'] == self.batch_id:
                    return batch['repositories']
            
            print(f"❌ Batch {self.batch_id} not found in configuration")
            return []
            
        except FileNotFoundError:
            print("❌ Batch config file not found: batch-config.json")
            return []
    
    def get_repo_config(self, repo_name, repo_values):
        """Get configuration for a specific repository"""
        # Extract repo name without org (e.g., "your-org/test-repo-1" -> "test-repo-1")
        repo_short = repo_name.split('/')[-1]
        
        # Get repo-specific values or fall back to default
        if repo_short in repo_values:
            config = repo_values[repo_short].copy()
            print(f"    📋 Using specific config for {repo_short}")
        else:
            config = repo_values['default'].copy()
            print(f"    📋 Using default config for {repo_short}")
        
        return config
    
    def render_workflow(self, repo_config):
        """Render the workflow template with repo-specific values"""
        try:
            return self.template.render(**repo_config)
        except Exception as e:
            print(f"    ❌ Template rendering failed: {str(e)}")
            return None
    
    def deploy_to_repo(self, repo_name, branches, file_location, create_prs, dry_run):
        """Deploy workflow to a single repository"""
        print(f"  🔄 Processing: {repo_name}")
        
        try:
            # Load configuration
            repo_values = self.load_repo_values()
            repo_config = self.get_repo_config(repo_name, repo_values)
            
            # Render workflow
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
            
            # Get repository
            github_repo = self.github.get_repo(repo_name)
            
            # Process each branch
            for branch in branches:
                try:
                    # Check if branch exists
                    github_repo.get_branch(branch)
                    print(f"    ✅ Branch '{branch}' exists")
                    
                    if create_prs:
                        # Create feature branch for PR
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
                    
                    # Create/update workflow file
                    self.create_workflow_file(
                        github_repo, 
                        file_location, 
                        workflow_content, 
                        target_branch
                    )
                    
                    # Create PR if needed
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
                            self.results['prs_created'].append({
                                'repo': repo_name,
                                'pr_number': pr.number,
                                'pr_url': pr.html_url,
                                'branch': branch
                            })
                    
                    print(f"    ✅ Success for branch: {branch}")
                    
                except Exception as e:
                    print(f"    ❌ Error with branch {branch}: {str(e)}")
                    self.results['failed'].append({
                        'repo': repo_name,
                        'branch': branch,
                        'error': str(e)
                    })
            
            self.results['successful'].append(repo_name)
            
        except Exception as e:
            print(f"    ❌ Repository error: {str(e)}")
            self.results['failed'].append({
                'repo': repo_name,
                'error': str(e)
            })
    
    def create_workflow_file(self, github_repo, file_path, content, branch):
        """Create or update workflow file in repository"""
        try:
            # Try to get existing file
            try:
                existing_file = github_repo.get_contents(file_path, ref=branch)
                # Update existing file
                github_repo.update_file(
                    path=file_path,
                    message="Update UltraTax workflow configuration",
                    content=content,
                    sha=existing_file.sha,
                    branch=branch
                )
                print(f"      ✅ Updated existing file: {file_path}")
            except:
                # Create new file
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
        """Create pull request for the workflow changes"""
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

### 🤖 Auto-generated
- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Batch ID: {self.batch_id}
- Repository: {repo_name}

---
*This PR was automatically created by the UltraTax Workflow Deployer*
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
        """Save batch processing results to files"""
        os.makedirs('output', exist_ok=True)
        
        # Save batch summary
        with open(f'output/batch-{self.batch_id}-summary.txt', 'w') as f:
            f.write(f"Batch {self.batch_id} Processing Results\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
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
        
        # Save PR list for this batch
        if self.results['prs_created']:
            with open(f'output/batch-{self.batch_id}-prs.txt', 'w') as f:
                f.write("# Format: repo,pr_number,pr_url,branch\n")
                for pr in self.results['prs_created']:
                    f.write(f"{pr['repo']},{pr['pr_number']},{pr['pr_url']},{pr['branch']}\n")
        
        # Save failures for this batch
        if self.results['failed']:
            with open(f'output/batch-{self.batch_id}-failures.txt', 'w') as f:
                f.write("# Format: repo,branch,error\n")
                for failure in self.results['failed']:
                    branch = failure.get('branch', 'N/A')
                    error = failure['error'].replace(',', ';')  # Escape commas in error messages
                    f.write(f"{failure['repo']},{branch},{error}\n")
        
        print(f"✅ Batch {self.batch_id} results saved to output/ directory")
    

    def deploy_batch(self, branches_input, file_location, create_prs, dry_run):
        """Deploy workflows to all repositories in this batch"""
        repositories = self.load_batch_repos()
        if not repositories:
            print(f"❌ No repositories found for batch {self.batch_id}")
            return
        
        branches = [b.strip() for b in branches_input.split(',') if b.strip()]
        
        print(f"🚀 Starting Batch {self.batch_id} Deployment")
        print(f"📦 Repositories in batch: {len(repositories)}")
        print(f"🎯 Target branches: {', '.join(branches)}")
        print(f"📁 File location: {file_location}")
        print(f"🔍 Dry run mode: {dry_run}")
        print(f"🔀 Create PRs: {create_prs}")
        print("-" * 50)
        
        for repo_name in repositories:
            self.deploy_to_repo(repo_name, branches, file_location, create_prs, dry_run)
            # Small delay to avoid rate limiting
            time.sleep(1)
        
        # Save results
        self.save_results()
        
        print(f"\n🎉 Batch {self.batch_id} completed!")
        print(f"✅ Successful: {len(self.results['successful'])}")
        print(f"❌ Failed: {len(self.results['failed'])}")
        print(f"🔀 PRs created: {len(self.results['prs_created'])}")

def main():
    parser = argparse.ArgumentParser(description='Deploy UltraTax workflows to a batch of repositories')
    parser.add_argument('--token', required=True, help='GitHub personal access token')
    parser.add_argument('--batch-id', type=int, required=True, help='Batch ID to process')
    parser.add_argument('--branches', required=True, help='Comma-separated list of target branches')
    parser.add_argument('--file-location', required=True, help='Target file location in repositories')
    parser.add_argument('--create-prs', default='true', help='Create pull requests (true/false)')
    parser.add_argument('--dry-run', default='false', help='Dry run mode (true/false)')
    
    args = parser.parse_args()
    
    # Convert string booleans
    create_prs = args.create_prs.lower() == 'true'
    dry_run = args.dry_run.lower() == 'true'
    
    deployer = SimpleWorkflowDeployer(args.token, args.batch_id)
    deployer.deploy_batch(args.branches, args.file_location, create_prs, dry_run)

if __name__ == "__main__":
    main()