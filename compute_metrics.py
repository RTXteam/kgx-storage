#!/usr/bin/env python3
"""
Precompute folder statistics for the KGX Storage web server.

Run this script periodically (e.g., via cron every hour) to update folder metrics.
The web server will read from the generated metrics.json file for instant page loads.

Usage:
    python compute_metrics.py
"""

import boto3
import json
import time
from datetime import datetime
from pathlib import Path

BUCKET_NAME = "translator-ingests"
METRICS_FILE = Path(__file__).parent / "metrics.json"
S3_CLIENT = boto3.client("s3")


def format_size(size_bytes):
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_folder_stats(prefix):
    """Calculate total size and file count for a folder."""
    paginator = S3_CLIENT.get_paginator("list_objects_v2")
    total_size = 0
    file_count = 0
    latest_modified = None

    try:
        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                total_size += obj.get("Size", 0)
                file_count += 1
                if latest_modified is None or obj["LastModified"] > latest_modified:
                    latest_modified = obj["LastModified"]
    except Exception as e:
        print(f"Error processing {prefix}: {e}")
        return None

    return {
        "size": total_size,
        "size_display": format_size(total_size),
        "file_count": file_count,
        "modified": latest_modified.strftime("%Y-%m-%d %H:%M") if latest_modified else "-"
    }


def discover_all_folders(max_depth=4):
    """Discover all folders in the bucket up to max_depth levels."""
    folders_to_process = [""]  # Start with root
    all_folders = set()

    while folders_to_process:
        prefix = folders_to_process.pop(0)
        depth = prefix.count("/")

        if depth >= max_depth:
            continue

        try:
            paginator = S3_CLIENT.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix, Delimiter="/"):
                # Get subfolders
                for prefix_obj in page.get("CommonPrefixes", []):
                    folder_path = prefix_obj["Prefix"]
                    all_folders.add(folder_path)
                    folders_to_process.append(folder_path)
        except Exception as e:
            print(f"Error discovering folders in {prefix}: {e}")
            continue

    return sorted(all_folders)


def compute_all_metrics():
    """Compute metrics for all folders and save to JSON file."""
    print(f"Starting metric computation at {datetime.now()}")
    print(f"Bucket: {BUCKET_NAME}")

    # Discover all folders
    print("Discovering folders...")
    folders = discover_all_folders()
    print(f"Found {len(folders)} folders to process")

    # Compute metrics for each folder
    metrics = {}
    total = len(folders)

    for idx, folder in enumerate(folders, 1):
        print(f"[{idx}/{total}] Processing: {folder}")
        stats = get_folder_stats(folder)
        if stats:
            metrics[folder] = stats

        # Progress update every 10 folders
        if idx % 10 == 0:
            print(f"Progress: {idx}/{total} ({idx/total*100:.1f}%)")

    # Add metadata
    output = {
        "computed_at": datetime.now().isoformat(),
        "bucket": BUCKET_NAME,
        "folder_count": len(metrics),
        "metrics": metrics
    }

    # Save to JSON file (atomic write)
    temp_file = METRICS_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(output, f, indent=2)

    # Atomic rename
    temp_file.replace(METRICS_FILE)

    print(f"\nCompleted at {datetime.now()}")
    print(f"Metrics saved to: {METRICS_FILE}")
    print(f"Total folders processed: {len(metrics)}")

    return metrics


if __name__ == "__main__":
    start_time = time.time()
    compute_all_metrics()
    elapsed = time.time() - start_time
    print(f"Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
