import argparse
import os
import xml.etree.ElementTree as ET
import urllib.parse
import time

from google.cloud import storage
from google.api_core import exceptions

from video_indexer import analyze_video
from generate_report import generate_visual_report

def download_and_parse_fcpxml(project_id, bucket_name, fcpxml_name):
    """
    Downloads an FCPXML file from GCS, parses it, and extracts video GCS URIs
    based on specified keywords.
    """
    print(f"Downloading {fcpxml_name} from gs://{bucket_name}...")
    try:
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(fcpxml_name)

        if not blob.exists():
            print(f"--- ERROR: FILE NOT FOUND ---")
            print(f"The file '{fcpxml_name}' was not found in the bucket '{bucket_name}'.")
            return []

        fcpxml_content = blob.download_as_string()
        root = ET.fromstring(fcpxml_content)
    except Exception as e:
        print(f"An unexpected error occurred during download/parsing: {e}")
        return []

    asset_map = {}
    for asset in root.findall('./resources/asset'):
        asset_id = asset.get('id')
        media_rep = asset.find('media-rep')
        if asset_id and media_rep is not None and media_rep.get('kind') == 'original-media':
            src = media_rep.get('src')
            if src:
                parsed_url = urllib.parse.urlparse(src)
                filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
                base_filename, _ = os.path.splitext(filename)
                new_filename = base_filename + ".mov"
                gcs_uri = f"gs://{bucket_name}/{new_filename}"
                asset_map[asset_id] = gcs_uri

    video_urls = []
    for asset_clip in root.findall('.//spine/asset-clip'):
        keywords = [kw.get('value') for kw in asset_clip.findall('keyword')]
        if "decor" in keywords or "guest" in keywords:
            asset_id_ref = asset_clip.get('ref')
            if asset_id_ref in asset_map:
                video_urls.append(asset_map[asset_id_ref])

    # Return a unique list of video URLs
    return sorted(list(set(video_urls)))


def get_processed_videos(results_file):
    """Reads the results file and returns a set of processed video URIs."""
    if not os.path.exists(results_file):
        return set()
    with open(results_file, 'r') as f:
        # Each line is a JSON URI, gs://bucket/video.json
        # We convert it back to the expected video URI, gs://bucket/video.mov
        processed_json_uris = [line.strip() for line in f]
        processed_video_uris = set()
        for json_uri in processed_json_uris:
            base_name, _ = os.path.splitext(json_uri)
            processed_video_uris.add(base_name + ".mov")
        return processed_video_uris

def main(project_id, bucket_name, fcpxml_name, results_file="analysis_results.txt", generate_report=False):
    """
    Main function to orchestrate video processing and report generation.
    """
    if generate_report:
        print("--- Generating Final Report ---")
        if not os.path.exists(results_file):
            print(f"Error: Results file '{results_file}' not found. Cannot generate report.")
            return
        with open(results_file, 'r') as f:
            json_uris = [line.strip() for line in f]

        if not json_uris:
            print("No analysis results found. Nothing to report.")
            return

        generate_visual_report(json_uris, project_id)
        print(f"\n--- Report generation complete. See report.html ---")
        return

    try:
        # Step 1: Get the full list of videos to process
        all_videos = download_and_parse_fcpxml(project_id, bucket_name, fcpxml_name)
        if not all_videos:
            return

        # Step 2: Get the list of videos that are already processed
        processed_videos = get_processed_videos(results_file)

        # Step 3: Determine the list of videos remaining to be processed
        videos_to_process = [v for v in all_videos if v not in processed_videos]

        if not videos_to_process:
            print("All videos have already been analyzed. Nothing to do.")
            print(f"To generate the final report, run: python3 {__file__} --project-id {project_id} --generate-report")
            return

        print(f"\nFound {len(all_videos)} total videos.")
        print(f"{len(processed_videos)} videos already processed.")
        print(f"Starting analysis for {len(videos_to_process)} remaining videos...")

        # Step 4: Process the remaining videos
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.bucket(bucket_name)

        for i, video_url in enumerate(videos_to_process):
            print(f"\n({i+1}/{len(videos_to_process)}) Processing: {video_url}")
            try:
                blob_name = video_url.replace(f"gs://{bucket_name}/", "")
                if not bucket.blob(blob_name).exists():
                    print(f"  -> Error: Video file not found. Skipping.")
                    continue

                print(f"  -> Found video. Starting analysis...")
                json_uri = analyze_video(video_url, project_id)

                # Append result immediately to the file to save progress
                with open(results_file, "a") as f:
                    f.write(f"{json_uri}\n")
                print(f"  -> Success! Result saved to {results_file}")

            except Exception as e:
                print(f"  -> An unexpected error occurred: {e}")
                continue

            time.sleep(1.1)

        print("\n--- Video processing complete ---")
        print(f"To generate the final report, run: python3 {__file__} --project-id {project_id} --generate-report")

    except Exception as e:
        print(f"A critical error occurred: {e}")
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process FCPXML videos from GCS.")
    parser.add_argument("--project-id", required=True, help="Google Cloud project ID.")
    parser.add_argument("--bucket-name", default="kaon123_bucket", help="GCS bucket name.")
    parser.add_argument("--fcpxml-name", default="Jennifer.fcpxml", help="FCPXML file name in GCS.")
    parser.add_argument("--generate-report", action="store_true", help="Generate final report from existing results.")
    args = parser.parse_args()

    main(args.project_id, args.bucket_name, args.fcpxml_name, generate_report=args.generate_report)