import os
import xml.etree.ElementTree as ET
from google.cloud import storage
import argparse

def download_gcs_file(project_id, bucket_name, source_blob_name, destination_file_name):
    """Downloads a file from Google Cloud Storage."""
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    print(f"Downloading {source_blob_name} from bucket {bucket_name}...")
    blob.download_to_filename(destination_file_name)
    print(f"File {source_blob_name} downloaded to {destination_file_name}.")

def search_fcpxml(file_path, keywords):
    """Parses an FCPXML file and searches for clips with keywords."""
    print(f"Performing a targeted search for keywords: {', '.join(keywords)} in {file_path}")

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return

    found_clip_names = set()
    lower_keywords = [k.lower() for k in keywords]

    # Search in various clip types
    for clip_type in ['clip', 'asset-clip', 'ref-clip', 'sync-clip', 'multicam-clip']:
        for clip in root.findall(f'.//{clip_type}'):
            clip_name = clip.get('name', f'Unnamed {clip_type}')

            # Check clip name
            if any(keyword in clip_name.lower() for keyword in lower_keywords):
                if clip_name not in found_clip_names:
                    print(clip_name)
                    found_clip_names.add(clip_name)
                continue

            # Check keyword elements
            for keyword_element in clip.findall('.//keyword'):
                keyword_value = keyword_element.get('value', '').lower()
                if any(keyword in keyword_value for keyword in lower_keywords):
                    if clip_name not in found_clip_names:
                        print(clip_name)
                        found_clip_names.add(clip_name)
                    break

            # Check notes
            for note_element in clip.findall('.//note'):
                if note_element.text and any(keyword in note_element.text.lower() for keyword in lower_keywords):
                    if clip_name not in found_clip_names:
                        print(clip_name)
                        found_clip_names.add(clip_name)
                    break

            # Check keywords attribute
            keywords_attr = clip.get('keywords', '').lower()
            if any(keyword in keywords_attr.split() for keyword in lower_keywords):
                 if clip_name not in found_clip_names:
                    print(clip_name)
                    found_clip_names.add(clip_name)

    if not found_clip_names:
        print("No clips found matching the keywords after a targeted search.")

def main():
    parser = argparse.ArgumentParser(description='Search FCPXML file in GCS for keywords.')
    parser.add_argument('--project_id', required=True, help='Your Google Cloud project ID.')
    parser.add_argument('--bucket_name', required=True, help='Your Google Cloud Storage bucket name.')
    parser.add_argument('--file_name', required=True, help='The FCPXML file name in the bucket.')
    args = parser.parse_args()

    keywords_to_search = ["decor", "guest"]
    local_file_path = "downloaded.fcpxml"

    try:
        download_gcs_file(args.project_id, args.bucket_name, args.file_name, local_file_path)

        search_fcpxml(local_file_path, keywords_to_search)
    finally:
        # Clean up the downloaded file
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
            print(f"\nCleaned up {local_file_path}.")

if __name__ == '__main__':
    main()