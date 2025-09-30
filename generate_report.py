import argparse
import json
import os
import tempfile
import uuid

import cv2
from google.cloud import storage
from jinja2 import Environment, FileSystemLoader

def classify_shot(box: dict) -> str:
    """Classifies a shot based on the bounding box's position and size."""
    if not box: return "Unknown"
    top, left, right = box.get('top', 0.0), box.get('left', 0.0), box.get('right', 0.0)
    horizontal_center = (left + right) / 2.0
    distance_from_side = left if horizontal_center < 0.5 else 1.0 - right
    distance_metric = top + distance_from_side
    if distance_metric < 0.05: return "Close-up Shot"
    if distance_metric > 0.5: return "Wide Shot"
    return "Medium Shot"

def generate_report_data(gcs_uris: list, project_id: str):
    """
    Generates a `report_data.json` file and uploads thumbnails to GCS.
    The JSON file contains all analysis metadata and public URLs to the thumbnails.
    """
    print(f"Starting report data generation for {len(gcs_uris)} video(s).")
    storage_client = storage.Client(project=project_id)
    all_videos_data = []

    # Create a temporary directory to store thumbnails before uploading
    with tempfile.TemporaryDirectory() as temp_dir:
        for gcs_uri in gcs_uris:
            print(f"\nProcessing: {gcs_uri}")
            try:
                if not gcs_uri.startswith("gs://"):
                    raise ValueError("Invalid GCS URI.")

                path_parts = gcs_uri[5:].split("/", 1)
                bucket_name, json_blob_name = path_parts[0], path_parts[1]
                bucket = storage_client.bucket(bucket_name)

                json_blob = bucket.blob(json_blob_name)
                if not json_blob.exists():
                    print(f"  -> Error: JSON file not found at {gcs_uri}. Skipping.")
                    continue

                json_data = json.loads(json_blob.download_as_string())

                video_blob_name, _ = os.path.splitext(json_blob_name)
                video_blob = bucket.blob(f"{video_blob_name}.mov")

                if not video_blob.exists():
                    raise FileNotFoundError(f"No corresponding video file found for {json_blob_name}")

                with tempfile.NamedTemporaryFile(suffix=".mov", delete=False) as temp_video_file:
                    video_blob.download_to_filename(temp_video_file.name)
                    video_path = temp_video_file.name

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    raise IOError(f"Could not open video file: {video_path}")

                tracked_objects = {}
                NUM_FRAMES_PER_SEGMENT = 5
                annotations = json_data.get('annotationResults', [{}])[0].get('objectAnnotations', [])

                for annotation in annotations:
                    entity = annotation.get('entity', {})
                    description = entity.get('description', 'unknown')

                    if description not in tracked_objects:
                        tracked_objects[description] = {'label': description.capitalize(), 'id': str(uuid.uuid4()), 'segments': []}

                    segment_data = annotation.get('segment', {})
                    start_time = float(segment_data.get('startTimeOffset', '0s').rstrip('s'))
                    end_time = float(segment_data.get('endTimeOffset', '0s').rstrip('s'))

                    shot_type = "N/A"
                    if description == 'person' and 'frames' in annotation and annotation['frames']:
                        shot_type = classify_shot(annotation['frames'][0].get('normalizedBoundingBox', {}))

                    thumbnail_urls = []
                    interval = (end_time - start_time) / NUM_FRAMES_PER_SEGMENT if NUM_FRAMES_PER_SEGMENT > 0 else 0
                    for i in range(NUM_FRAMES_PER_SEGMENT):
                        time_pos_ms = (start_time + (i * interval)) * 1000
                        cap.set(cv2.CAP_PROP_POS_MSEC, time_pos_ms)
                        success, frame = cap.read()
                        if success:
                            thumb_filename = f"{uuid.uuid4()}.jpg"
                            local_thumb_path = os.path.join(temp_dir, thumb_filename)
                            cv2.imwrite(local_thumb_path, frame)

                            # Upload to GCS
                            gcs_thumb_path = f"thumbnails/{thumb_filename}"
                            thumb_blob = bucket.blob(gcs_thumb_path)
                            thumb_blob.upload_from_filename(local_thumb_path)
                            # The make_public() call is removed as the bucket now has a public access policy.
                            thumbnail_urls.append(thumb_blob.public_url)

                    tracked_objects[description]['segments'].append({
                        'start_time': start_time, 'end_time': end_time, 'shot_type': shot_type,
                        'confidence': annotation.get('confidence', 0), 'thumbnails': thumbnail_urls
                    })

                cap.release()
                os.remove(video_path)

                all_videos_data.append({
                    "video_file": video_blob.name,
                    "tracked_objects": dict(sorted(tracked_objects.items()))
                })

            except Exception as e:
                print(f"Error processing {gcs_uri}: {e}")
                continue

    if not all_videos_data:
        print("No data was processed to generate the report data.")
        return

    # Write the final JSON data file
    report_data_filename = 'report_data.json'
    with open(report_data_filename, 'w') as f:
        json.dump(all_videos_data, f, indent=4)
    print(f"\nSuccessfully generated report data: {report_data_filename}")
    print("Thumbnails have been uploaded to the 'thumbnails/' directory in your bucket.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generates report_data.json and uploads thumbnails from analysis files.")
    parser.add_argument("gcs_uris", nargs='+', help='One or more GCS URIs of JSON analysis files.')
    parser.add_argument("--project-id", required=True, help="Your Google Cloud project ID.")
    args = parser.parse_args()
    generate_report_data(args.gcs_uris, args.project_id)