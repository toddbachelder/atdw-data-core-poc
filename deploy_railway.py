#!/usr/bin/env python3
"""
Deploy ATDW Data Probe API to Railway.app using the Railway API.

Requirements:
  - Railway account + API token (create at railway.app/account/tokens)
  - GitHub token (optional, but helpful)
  - DATABASE_URL from Supabase

Usage:
  python deploy_railway.py
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================

RAILWAY_API = "https://api.railway.app/graphql"
GITHUB_REPO = "atdw-data-core-poc"  # Your repo name
GITHUB_OWNER = None  # Will be prompted
PROJECT_NAME = "atdw-probe-api"

# ============================================================================
# Helpers
# ============================================================================

def prompt(message: str, default: Optional[str] = None) -> str:
    """Prompt user for input."""
    suffix = f" [{default}]" if default else ""
    resp = input(f"{message}{suffix}: ").strip()
    return resp if resp else default


def load_env() -> dict:
    """Load .env file."""
    env_path = Path(".env")
    if not env_path.exists():
        print("ERROR: .env not found. Create it with: cp .env.example .env")
        sys.exit(1)

    env = {}
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def railway_query(token: str, query: str, variables: dict = None) -> dict:
    """Execute GraphQL query against Railway API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        resp = requests.post(RAILWAY_API, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            print(f"GraphQL Error: {data['errors']}")
            return {}

        return data.get("data", {})

    except Exception as e:
        print(f"API Error: {e}")
        return {}


# ============================================================================
# Deployment Steps
# ============================================================================

def create_project(token: str, github_owner: str) -> Optional[str]:
    """Create a new Railway project."""
    print(f"\n[1/5] Creating Railway project '{PROJECT_NAME}'...")

    query = """
    mutation CreateProject($input: CreateProjectInput!) {
        projectCreate(input: $input) {
            project {
                id
                name
            }
        }
    }
    """

    variables = {"input": {"name": PROJECT_NAME}}
    result = railway_query(token, query, variables)

    if "projectCreate" in result:
        project_id = result["projectCreate"]["project"]["id"]
        print(f"    ✓ Project created: {project_id}")
        return project_id

    print("    ✗ Failed to create project")
    return None


def connect_github(token: str, project_id: str, github_owner: str) -> Optional[str]:
    """Connect GitHub repo to the project."""
    print(f"\n[2/5] Connecting GitHub repo {github_owner}/{GITHUB_REPO}...")

    query = """
    mutation CreateGitHubIntegration($input: CreateGitHubIntegrationInput!) {
        githubIntegrationCreate(input: $input) {
            integration {
                id
            }
        }
    }
    """

    variables = {
        "input": {
            "projectId": project_id,
            "repo": f"{github_owner}/{GITHUB_REPO}",
            "branch": "itinerary-accessible-ev-roadtrip",
        }
    }

    result = railway_query(token, query, variables)

    if "githubIntegrationCreate" in result:
        integration_id = result["githubIntegrationCreate"]["integration"]["id"]
        print(f"    ✓ GitHub connected: {integration_id}")
        return integration_id

    print("    ✗ Failed to connect GitHub (you may need to do this manually via dashboard)")
    return None


def create_environment(token: str, project_id: str) -> Optional[str]:
    """Create a production environment."""
    print(f"\n[3/5] Creating production environment...")

    query = """
    mutation CreateEnvironment($input: CreateEnvironmentInput!) {
        environmentCreate(input: $input) {
            environment {
                id
                name
            }
        }
    }
    """

    variables = {
        "input": {
            "projectId": project_id,
            "name": "production",
        }
    }

    result = railway_query(token, query, variables)

    if "environmentCreate" in result:
        env_id = result["environmentCreate"]["environment"]["id"]
        print(f"    ✓ Environment created: {env_id}")
        return env_id

    print("    ✗ Failed to create environment")
    return None


def add_variables(token: str, project_id: str, env_id: str, database_url: str) -> bool:
    """Add environment variables to the project."""
    print(f"\n[4/5] Adding environment variables...")

    query = """
    mutation UpsertVariable($input: UpsertVariableInput!) {
        variableUpsert(input: $input) {
            variable {
                id
                name
                value
            }
        }
    }
    """

    variables_to_add = {
        "DATABASE_URL": database_url,
    }

    for var_name, var_value in variables_to_add.items():
        variables = {
            "input": {
                "projectId": project_id,
                "environmentId": env_id,
                "name": var_name,
                "value": var_value,
            }
        }

        result = railway_query(token, query, variables)

        if "variableUpsert" in result:
            print(f"    ✓ {var_name} added")
        else:
            print(f"    ✗ Failed to add {var_name}")
            return False

    return True


def trigger_deployment(token: str, project_id: str) -> bool:
    """Trigger a deployment from the latest git commit."""
    print(f"\n[5/5] Triggering deployment...")

    # Note: Railway auto-deploys on git push, but we can also trigger manually
    # For now, inform the user that they should push to GitHub

    print("    ℹ  Railway will auto-deploy on the next git push")
    print("    → Run: git push")
    print("    → Then check: railway.app/dashboard")

    return True


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("ATDW Data Probe — Deploy to Railway.app")
    print("=" * 70)

    # Load environment
    env = load_env()
    database_url = env.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in .env")
        sys.exit(1)

    print(f"\n✓ Loaded .env")
    print(f"  DATABASE_URL: {database_url[:50]}...")

    # Get Railway token
    print("\n" + "=" * 70)
    print("STEP 1: Railway Authentication")
    print("=" * 70)
    print("Go to: https://railway.app/account/tokens")
    print("Create a new token and paste it below:")

    railway_token = prompt("Railway API Token", default=os.environ.get("RAILWAY_TOKEN", ""))
    if not railway_token:
        print("ERROR: Railway token required")
        sys.exit(1)

    # Get GitHub owner
    print("\n" + "=" * 70)
    print("STEP 2: GitHub Configuration")
    print("=" * 70)

    github_owner = prompt(
        "GitHub username/organization",
        default=os.environ.get("GITHUB_USER", ""),
    )
    if not github_owner:
        print("ERROR: GitHub owner required")
        sys.exit(1)

    # Confirm
    print("\n" + "=" * 70)
    print("CONFIRMATION")
    print("=" * 70)
    print(f"  Project name:    {PROJECT_NAME}")
    print(f"  GitHub repo:     {github_owner}/{GITHUB_REPO}")
    print(f"  GitHub branch:   itinerary-accessible-ev-roadtrip")
    print(f"  Database:        Supabase (via DATABASE_URL)")

    if prompt("\nProceed? (yes/no)", default="yes").lower() not in ("yes", "y"):
        print("Cancelled.")
        sys.exit(0)

    # Deploy
    print("\n" + "=" * 70)
    print("DEPLOYING")
    print("=" * 70)

    project_id = create_project(railway_token, github_owner)
    if not project_id:
        sys.exit(1)

    integration_id = connect_github(railway_token, project_id, github_owner)
    # GitHub connection might fail; continue anyway

    env_id = create_environment(railway_token, project_id)
    if not env_id:
        sys.exit(1)

    if not add_variables(railway_token, project_id, env_id, database_url):
        print("WARNING: Some variables failed to add")

    if not trigger_deployment(railway_token, project_id):
        print("WARNING: Deployment trigger failed")

    # Summary
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print(f"1. Go to: https://railway.app/dashboard")
    print(f"2. Find your project: {PROJECT_NAME}")
    print(f"3. Push to git to trigger auto-deploy:")
    print(f"   git push")
    print(f"4. Watch the Build log in Railway dashboard")
    print(f"5. Once deployed, visit: https://your-url/docs")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
