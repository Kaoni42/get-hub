import argparse
import os
import xml.etree.ElementTree as ET

from google.cloud import storage
from google.api_core import exceptions

from video_indexer import analyze_video
from generate_report import generate_visual_report


def download_and_parse_fcpxml(project_id, bucket_name, fcpxml_name):
    """
    Downloads an FCPXML file from GCS, parses it, and extracts video URLs
    based on specified keywords.
    """
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(fcpxml_name)

    print(f"Downloading {fcpxml_name} from bucket {bucket_name}...")
    fcpxml_content = blob.download_as_string()

    root = ET.fromstring(fcpxml_content)
    namespaces = {'': 'http://www.apple.com/fcpxml-v1.0'}

    video_urls = []
    # Find all asset elements
    for asset in root.findall('.//asset', namespaces):
        keywords = [kw.get('value') for kw in asset.findall('keyword', namespaces)]
        if "decor" in keywords or "guest" in keywords:
            media_rep = asset.find('media-rep', namespaces)
            if media_rep is not None and media_rep.get('kind') == 'original-media':
                src = media_rep.get('src')
                if src:
                    # Assuming the src is a GCS URI, if not, this might need adjustment
                    video_urls.append(src)

    print(f"Found {len(video_urls)} videos with 'decor' or 'guest' keywords.")
    return video_urls


def diagnose_fcpxml(project_id, bucket_name, fcpxml_name):
    """
    Downloads and prints a detailed summary of an FCPXML file for diagnostic purposes,
    including file headers and namespace checks.
    """
    print(f"--- FCPXML DIAGNOSTIC MODE ---")
    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(fcpxml_name)

        if not blob.exists():
            print(f"Error: The file '{fcpxml_name}' was not found in the bucket '{bucket_name}'.")
            return

        print(f"Downloading {fcpxml_name} from bucket {bucket_name}...")
        fcpxml_content_bytes = blob.download_as_string()
        fcpxml_content_str = fcpxml_content_bytes.decode('utf-8')

        print("\n--- File Header (First 10 Lines) ---")
        header_lines = fcpxml_content_str.splitlines()[:10]
        for line in header_lines:
            print(line)
        print("------------------------------------")

        root = ET.fromstring(fcpxml_content_bytes)

        # Attempt 1: With standard FCPXML namespace
        print("\nAttempt 1: Searching for <asset> tags with standard namespace (http://www.apple.com/fcpxml-v1.0)...")
        namespaces = {'': 'http://www.apple.com/fcpxml-v1.0'}
        assets_with_ns = root.findall('.//asset', namespaces)

        if assets_with_ns:
            print(f"Success! Found {len(assets_with_ns)} assets with the standard namespace.")
            print_asset_summary(assets_with_ns, namespaces)
        else:
            print("Result: No <asset> elements found with the standard namespace.")

        # Attempt 2: Without any namespace
        print("\nAttempt 2: Searching for <asset> tags without a namespace...")
        assets_no_ns = root.findall('.//asset')

        if assets_no_ns and not assets_with_ns:
            print(f"Success! Found {len(assets_no_ns)} assets without a namespace.")
            print_asset_summary(assets_no_ns)
        else:
            print("Result: No <asset> elements found without a namespace.")

        if not assets_with_ns and not assets_no_ns:
            print("\nConclusion: The script could not find any <asset> tags. This is likely because the XML namespace is non-standard or the file is not a valid FCPXML.")

        print("\n--- DIAGNOSTIC COMPLETE ---")

    except ET.ParseError as e:
        print(f"\nXML PARSE ERROR: The file '{fcpxml_name}' could not be parsed. It may be corrupted or not a valid XML file.")
        print(f"Error details: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during diagnosis: {e}")

def print_asset_summary(assets, namespaces=None):
    """Helper function to print a summary of found assets."""
    print("-" * 20)
    for i, asset in enumerate(assets):
        asset_name = asset.get('name', 'N/A')

        # Find media-rep with or without namespace
        media_rep_finder = asset.find if namespaces else lambda path: asset.find(path, namespaces)
        media_rep = media_rep_finder('media-rep')
        asset_src = media_rep.get('src') if media_rep is not None else 'N/A'

        # Find keywords with or without namespace
        keyword_finder = asset.findall if namespaces else lambda path: asset.findall(path, namespaces)
        keywords = [kw.get('value') for kw in keyword_finder('keyword')]

        print(f"Asset {i+1}:")
        print(f"  - Name: {asset_name}")
        print(f"  - Source: {asset_src}")
        print(f"  - Keywords: {', '.join(keywords) if keywords else 'None'}")
        print("-" * 20)


def main(project_id, bucket_name, fcpxml_name, diagnose_fcpxml_flag):
    """
    Main function to orchestrate the FCPXML processing, video analysis, and report generation.
    """
    if diagnose_fcpxml_flag:
        diagnose_fcpxml(project_id, bucket_name, fcpxml_name)
        return

    try:
        print("Starting FCPXML processing workflow...")
        # Step 1 & 2: Download, parse the FCPXML file, and extract video URLs
        video_urls = download_and_parse_fcpxml(project_id, bucket_name, fcpxml_name)

        if not video_urls:
            print("No videos found with the specified keywords. Exiting.")
            return

        # Step 3: Analyze videos and collect JSON URIs
        json_uris = []
        for video_url in video_urls:
            print(f"Analyzing video: {video_url}")
            try:
                json_uri = analyze_video(video_url, project_id)
                json_uris.append(json_uri)
            except Exception as e:
                print(f"Error analyzing video {video_url}: {e}")
                continue

        if not json_uris:
            print("No videos were successfully analyzed. Exiting.")
            return

        # Step 4: Generate the HTML report
        print(f"\nGenerating consolidated report for {len(json_uris)} video(s)...")
        generate_visual_report(json_uris, project_id)

        print("\nWorkflow complete. The final report has been saved as report.html.")

    except exceptions.Unauthorized:
        error_message = f"""
--- AUTHENTICATION ERROR ---
The script failed to authenticate with Google Cloud, resulting in a 401 Unauthorized error.

This is usually caused by one of two things:
1.  You have not authenticated your local environment.
    - Please run the following command in your terminal and follow the prompts:
      gcloud auth application-default login

2.  Your authenticated user or service account does not have the required IAM permissions.
    - Please ensure your account has the following roles (or equivalent permissions):
      - 'Storage Object Viewer' on the bucket '{bucket_name}' (or the project).
      - 'Video Intelligence User' on the project '{project_id}'.

After checking your authentication and permissions, please try running the script again.
"""
        print(error_message)
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process an FCPXML file, analyze videos, and generate a report."
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Your Google Cloud project ID.",
    )
    parser.add_argument(
        "--bucket-name",
        default="kaon123_bucket",
        help="The GCS bucket where the FCPXML file is located.",
    )
    parser.add_argument(
        "--fcpxml-name",
        default="Jennifer.fcpxml",
        help="The name of the FCPXML file to process.",
    )
    parser.add_argument(
        "--diagnose-fcpxml",
        action="store_true",
        help="Run in FCPXML diagnostic mode. Prints a summary of assets and keywords and exits.",
    )
    args = parser.parse_args()
    main(args.project_id, args.bucket_name, args.fcpxml_name, args.diagnose_fcpxml)