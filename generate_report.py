import argparse
import base64
import json
import os
import tempfile
import uuid

import cv2
from google.cloud import storage
from jinja2 import Environment, FileSystemLoader


def classify_shot(box: dict) -> str:
    """
    Classifies a shot based on the bounding box's position and size.

    Args:
        box: A dictionary representing the normalized bounding box.

    Returns:
        A string classification: "Close-up", "Medium", or "Wide".
    """
    if not box:
        return "Unknown"

    top = box.get('top', 0.0)
    left = box.get('left', 0.0)
    right = box.get('right', 0.0)

    # Calculate distance from the nearest vertical edge
    horizontal_center = (left + right) / 2.0
    if horizontal_center < 0.5:
        distance_from_side = left
    else:
        distance_from_side = 1.0 - right

    # New classification logic
    distance_metric = top + distance_from_side
    if distance_metric < 0.05:
        return "Close-up Shot"
    elif distance_metric > 0.5:
        return "Wide Shot"
    else:
        return "Medium Shot"


def generate_visual_report(gcs_uris: list, project_id: str, diagnose: bool = False):
    """
    Generates a consolidated HTML report from a list of Video Intelligence JSON analysis files.
    """
    print(f"Starting report generation for {len(gcs_uris)} video(s).")
    storage_client = storage.Client(project=project_id)
    all_videos_data = []

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
            # Use the .mov extension for the video file as per previous logic
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
            NUM_FRAMES_PER_SEGMENT = 15
            annotations = json_data.get('annotationResults', [{}])[0].get('objectAnnotations', [])

            for annotation in annotations:
                entity = annotation.get('entity', {})
                description = entity.get('description', 'unknown')

                if description not in tracked_objects:
                    tracked_objects[description] = {
                        'label': description.capitalize(),
                        'id': str(uuid.uuid4()),
                        'segments': []
                    }

                segment_data = annotation.get('segment', {})
                start_time = float(segment_data.get('startTimeOffset', '0s').rstrip('s'))
                end_time = float(segment_data.get('endTimeOffset', '0s').rstrip('s'))

                shot_type = "N/A"
                if description == 'person' and 'frames' in annotation and annotation['frames']:
                    shot_type = classify_shot(annotation['frames'][0].get('normalizedBoundingBox', {}))

                thumbnails_list = []
                interval = (end_time - start_time) / NUM_FRAMES_PER_SEGMENT if NUM_FRAMES_PER_SEGMENT > 0 else 0
                for i in range(NUM_FRAMES_PER_SEGMENT):
                    time_pos_ms = (start_time + (i * interval)) * 1000
                    cap.set(cv2.CAP_PROP_POS_MSEC, time_pos_ms)
                    success, frame = cap.read()
                    if success:
                        _, buffer = cv2.imencode('.jpg', frame)
                        thumbnails_list.append(base64.b64encode(buffer).decode('utf-8'))

                tracked_objects[description]['segments'].append({
                    'start_time': start_time, 'end_time': end_time, 'shot_type': shot_type,
                    'confidence': annotation.get('confidence', 0), 'thumbnails': thumbnails_list
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
        print("No data was processed to generate a report.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(script_dir))
    template = env.get_template('template.html')
    html_content = template.render(all_videos_data=all_videos_data)

    report_filename = 'report.html'
    with open(report_filename, 'w') as f:
        f.write(html_content)
    print(f"\nSuccessfully generated consolidated report: {report_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates a consolidated HTML report from multiple Google Video Intelligence analysis files."
    )
    parser.add_argument(
        "gcs_uris",
        nargs='+',
        help='One or more GCS URIs of JSON analysis files (e.g., "gs://bucket/video.json").',
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Your Google Cloud project ID.",
    )
    args = parser.parse_args()
    generate_visual_report(args.gcs_uris, args.project_id)