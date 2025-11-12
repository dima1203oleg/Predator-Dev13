#!/usr/bin/env python3
"""
Script to fix missing Helm chart values sections that cause nil pointer errors.
Adds missing image, service, autoscaling, and serviceAccount sections to all values.yaml files.
"""

import os
import yaml
import glob

def load_yaml(file_path):
    """Load YAML file safely."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def save_yaml(file_path, data):
    """Save YAML file safely."""
    try:
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        print(f"Updated {file_path}")
    except Exception as e:
        print(f"Error saving {file_path}: {e}")

def add_missing_sections(values_file):
    """Add missing sections to values.yaml file."""
    data = load_yaml(values_file)
    if not data:
        return

    modified = False

    # Add image section if missing
    if 'image' not in data:
        data['image'] = {
            'repository': 'nginx',  # default, will be overridden by specific charts
            'tag': 'latest',
            'pullPolicy': 'IfNotPresent'
        }
        modified = True

    # Add service section if missing
    if 'service' not in data:
        data['service'] = {
            'type': 'ClusterIP',
            'port': 80  # default, will be overridden by specific charts
        }
        modified = True

    # Add autoscaling section if missing
    if 'autoscaling' not in data:
        data['autoscaling'] = {
            'enabled': False,
            'minReplicas': 1,
            'maxReplicas': 3,
            'targetCPUUtilizationPercentage': 80
        }
        modified = True

    # Add serviceAccount section if missing
    if 'serviceAccount' not in data:
        data['serviceAccount'] = {
            'create': True,
            'name': ''
        }
        modified = True

    if modified:
        save_yaml(values_file, data)

def main():
    """Main function to process all values.yaml files."""
    charts_dir = "/Users/dima/Documents/Predator analitycs 13/helm/predator-umbrella/charts"
    values_files = glob.glob(os.path.join(charts_dir, "**/values.yaml"), recursive=True)

    print(f"Found {len(values_files)} values.yaml files")

    # Skip charts that already have these sections (redis, postgres, opensearch)
    skip_charts = ['redis', 'postgres', 'opensearch']

    for values_file in values_files:
        chart_name = os.path.basename(os.path.dirname(values_file))
        if chart_name not in skip_charts:
            print(f"Processing {chart_name}...")
            add_missing_sections(values_file)

    print("Done processing all charts")

if __name__ == "__main__":
    main()