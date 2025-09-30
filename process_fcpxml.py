import argparse
import os
import xml.etree.ElementTree as ET

from google.cloud import storage

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