import argparse
import os
import xml.etree.ElementTree as ET
import urllib.parse

from google.cloud import storage
from google.api_core import exceptions

from video_indexer import analyze_video
from generate_report import generate_visual_report


def parse_fcpxml_from_file(fcpxml_path, bucket_name):
    """
    Parses a local FCPXML file and constructs GCS URIs for videos
    based on specified keywords.
    """
    print(f"Parsing {fcpxml_path} to find videos with 'decor' or 'guest' keywords...")
    try:
        tree = ET.parse(fcpxml_path)
    except ET.ParseError as e:
        print(f"XML Parse Error: Could not parse {fcpxml_path}. Details: {e}")
        return []

    root = tree.getroot()

    # Create a dictionary to map asset IDs to their GCS URIs
    asset_map = {}
    # Find all asset elements in the resources section
    for asset in root.findall('./resources/asset'):
        asset_id = asset.get('id')
        media_rep = asset.find('media-rep')
        if asset_id and media_rep is not None and media_rep.get('kind') == 'original-media':
            src = media_rep.get('src')
            if src:
                # The src is a file URI, e.g., file:///path/to/My%20Clip.mov
                # We need to extract the filename and construct a GCS URI.
                parsed_url = urllib.parse.urlparse(src)
                # Unquote to handle spaces etc, then get the base name
                filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
                gcs_uri = f"gs://{bucket_name}/{filename}"
                asset_map[asset_id] = gcs_uri

    video_urls = []
    # Find all asset-clips in the timeline's spine
    for asset_clip in root.findall('.//spine/asset-clip'):
        # Find all keyword tags within the asset-clip
        keywords = [kw.get('value') for kw in asset_clip.findall('keyword')]
        if "decor" in keywords or "guest" in keywords:
            asset_id_ref = asset_clip.get('ref')
            if asset_id_ref in asset_map:
                video_urls.append(asset_map[asset_id_ref])
            else:
                print(f"Warning: Found an asset-clip with ref '{asset_id_ref}' but no matching asset in resources.")

    print(f"Found {len(video_urls)} video(s) to analyze:")
    for url in video_urls:
        print(f"- {url}")

    return video_urls


def diagnose_fcpxml_local(fcpxml_path):
    """
    Reads and prints a detailed summary of a local FCPXML file for diagnostic purposes.
    """
    print(f"--- FCPXML DIAGNOSTIC MODE (Local File) ---")
    try:
        with open(fcpxml_path, 'r', encoding='utf-8') as f:
            fcpxml_content_str = f.read()

        print("\n--- File Header (First 10 Lines) ---")
        header_lines = fcpxml_content_str.splitlines()[:10]
        for line in header_lines:
            print(line)
        print("------------------------------------")

        root = ET.fromstring(fcpxml_content_str)

        # Check for asset-clips and keywords, which is the actual logic needed
        print("\nChecking for <asset-clip> tags with <keyword> children...")
        asset_clips = root.findall('.//spine/asset-clip')

        if not asset_clips:
            print("Result: No <asset-clip> elements found in the spine. The timeline might be empty or structured differently.")
        else:
            print(f"Found {len(asset_clips)} asset-clips in the spine.")
            found_keywords = False
            for i, clip in enumerate(asset_clips):
                clip_name = clip.get('name', 'N/A')
                keywords = [kw.get('value') for kw in clip.findall('keyword')]
                if keywords:
                    found_keywords = True
                    print(f"  - Clip {i+1} ('{clip_name}') has keywords: {', '.join(keywords)}")
            if not found_keywords:
                print("Result: Found asset-clips, but none of them contained <keyword> tags.")

        print("\n--- DIAGNOSTIC COMPLETE ---")

    except FileNotFoundError:
        print(f"Error: The file '{fcpxml_path}' was not found.")
    except ET.ParseError as e:
        print(f"\nXML PARSE ERROR: The file '{fcpxml_path}' could not be parsed. It may be corrupted or not a valid XML file.")
        print(f"Error details: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during diagnosis: {e}")


def main(project_id, bucket_name, fcpxml_name, diagnose_fcpxml_flag):
    """
    Main function to orchestrate the FCPXML processing, video analysis, and report generation.
    """
    # Construct an absolute path to the FCPXML file, assuming it's in the same directory as the script.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fcpxml_path = os.path.join(script_dir, fcpxml_name)

    if diagnose_fcpxml_flag:
        diagnose_fcpxml_local(fcpxml_path)
        return

    try:
        print("Starting FCPXML processing workflow...")
        # Step 1 & 2: Parse the local FCPXML file and extract video GCS URIs
        video_urls = parse_fcpxml_from_file(fcpxml_path, bucket_name)

        if not video_urls:
            print("No videos found with the specified keywords. Exiting.")
            return

        # Step 3: Analyze videos and collect JSON URIs
        json_uris = []
        for video_url in video_urls:
            print(f"\nAnalyzing video: {video_url}")
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
This can happen if you have not authenticated your environment or if the
credentials do not have the required permissions.

To authenticate, you can use one of the following methods:
1.  Run `gcloud auth application-default login` in your terminal.
2.  Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path
    of your service account key file.

Please ensure your principal has the following IAM roles:
- 'Video Intelligence User' on project '{project_id}'
- 'Storage Object Viewer' on the video files in bucket '{bucket_name}'
- 'Storage Object Creator' on the bucket used for Video Indexer output.
"""
        print(error_message)
        return
    except FileNotFoundError:
        print(f"--- FILE NOT FOUND ERROR ---")
        print(f"The FCPXML file '{fcpxml_path}' was not found.")
        print("Please ensure the file exists in the same directory as the script and try again.")
        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process a local FCPXML file, analyze referenced videos from GCS, and generate a report."
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Your Google Cloud project ID.",
    )
    parser.add_argument(
        "--bucket-name",
        default="kaon123_bucket",
        help="The GCS bucket where the video files are located.",
    )
    parser.add_argument(
        "--fcpxml-name",
        default="Jennifer.fcpxml",
        help="The name of the local FCPXML file to process.",
    )
    parser.add_argument(
        "--diagnose-fcpxml",
        action="store_true",
        help="Run in FCPXML diagnostic mode. Prints a summary of assets and keywords and exits.",
    )
    args = parser.parse_args()
    main(args.project_id, args.bucket_name, args.fcpxml_name, args.diagnose_fcpxml)