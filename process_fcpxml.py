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


def main(project_id, bucket_name, fcpxml_name):
    """
    Main function to orchestrate the FCPXML processing, video analysis, and report generation.
    """
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
    args = parser.parse_args()
    main(args.project_id, args.bucket_name, args.fcpxml_name)