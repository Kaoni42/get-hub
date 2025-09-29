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
    if distance_metric < 0.15:
        return "Close-up Shot"
    elif distance_metric > 0.5:
        return "Wide Shot"
    else:
        return "Medium Shot"


def generate_report(gcs_uri: str, project_id: str, diagnose: bool = False):
    """
    Generates an HTML report from a Video Intelligence JSON analysis file
    or runs in diagnostic mode to print the JSON structure.

    Args:
        gcs_uri: The GCS URI of the JSON analysis file.
        project_id: The Google Cloud project ID.
        diagnose: If True, prints the JSON structure and exits.
    """
    print(f"Starting process for {gcs_uri}")

    # Initialize GCS client
    storage_client = storage.Client(project=project_id)

    # Parse GCS URI
    if not gcs_uri.startswith("gs://"):
        raise ValueError("Invalid GCS URI. Must start with 'gs://'")

    path_parts = gcs_uri[5:].split("/", 1)
    bucket_name = path_parts[0]
    json_blob_name = path_parts[1]

    bucket = storage_client.bucket(bucket_name)

    # Download JSON analysis file
    print(f"Downloading JSON file: {json_blob_name}")
    json_blob = bucket.blob(json_blob_name)
    try:
        json_data = json.loads(json_blob.download_as_string())
    except Exception as e:
        print(f"Error downloading or parsing JSON file: {e}")
        return

    # --- DIAGNOSTIC MODE ---
    if diagnose:
        output_filename = "diagnostic_output.json"
        print(f"\n--- DIAGNOSTIC MODE ---")
        with open(output_filename, "w") as f:
            json.dump(json_data, f, indent=4)
        print(f"Diagnostic data saved to '{output_filename}'.")
        print("Please copy the contents of this file and provide it in your response.")
        print("--- END DIAGNOSTIC MODE ---\n")
        return

    # Determine video file name
    video_blob_name, _ = os.path.splitext(json_blob_name)
    possible_video_extensions = ['.mp4', '.mov', '.avi', '.mpg', '.mkv']
    video_blob = None
    for ext in possible_video_extensions:
        potential_video_blob_name = video_blob_name + ext
        blob = bucket.blob(potential_video_blob_name)
        if blob.exists():
            video_blob = blob
            break

    if not video_blob:
        raise FileNotFoundError(f"Could not find a corresponding video file for {json_blob_name} in bucket {bucket_name}")

    print(f"Found corresponding video file: {video_blob.name}")

    # Download video to a temporary file
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(video_blob.name)[1], delete=False) as temp_video_file:
        print(f"Downloading video to temporary file: {temp_video_file.name}")
        video_blob.download_to_filename(temp_video_file.name)
        video_path = temp_video_file.name

    # --- Process Video, Group Annotations, and Generate Thumbnails ---
    print("Processing video to group objects, classify shots, and generate thumbnails...")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video file: {video_path}")

    tracked_objects = {}
    NUM_FRAMES_PER_SEGMENT = 15

    annotations = json_data.get('annotationResults', [{}])[0].get('objectAnnotations', [])
    print(f"Found {len(annotations)} object annotations to process.")

    for annotation in annotations:
        entity = annotation.get('entity', {})
        description = entity.get('description')
        if not description:
            continue

        # Group by description since trackId is not reliable
        group_key = description
        if group_key not in tracked_objects:
            tracked_objects[group_key] = {
                'label': description.capitalize(),
                'id': str(uuid.uuid4()), # Generate a unique ID for the group
                'segments': []
            }

        segment_data = annotation.get('segment', {})
        start_time_str = segment_data.get('startTimeOffset', '0s')
        end_time_str = segment_data.get('endTimeOffset', '0s')
        start_time = float(start_time_str.rstrip('s'))
        end_time = float(end_time_str.rstrip('s'))
        duration = end_time - start_time

        shot_type = "N/A"
        # Use the new shot classification logic for 'person' objects
        if description == 'person' and 'frames' in annotation and annotation['frames']:
            first_frame_box = annotation['frames'][0].get('normalizedBoundingBox', {})
            shot_type = classify_shot(first_frame_box)

        thumbnails_list = []
        if duration > 0.1:
            interval = duration / NUM_FRAMES_PER_SEGMENT
            for i in range(NUM_FRAMES_PER_SEGMENT):
                time_pos_ms = (start_time + (i * interval)) * 1000
                cap.set(cv2.CAP_PROP_POS_MSEC, time_pos_ms)
                success, frame = cap.read()
                if success:
                    _, buffer = cv2.imencode('.jpg', frame)
                    thumbnails_list.append(base64.b64encode(buffer).decode('utf-8'))

        if not thumbnails_list:
            cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)
            success, frame = cap.read()
            if success:
                _, buffer = cv2.imencode('.jpg', frame)
                thumbnails_list.append(base64.b64encode(buffer).decode('utf-8'))

        if not thumbnails_list:
            print(f"Warning: Could not generate thumbnail for {description} at {start_time}s")
            thumbnails_list.append("")

        tracked_objects[group_key]['segments'].append({
            'start_time': start_time,
            'end_time': end_time,
            'shot_type': shot_type,
            'confidence': annotation.get('confidence', 0),
            'thumbnails': thumbnails_list
        })

    cap.release()
    os.remove(video_path)
    print("Finished processing and grouping objects.")

    # --- Render HTML Report ---
    print("Rendering HTML report...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(script_dir))
    template = env.get_template('template.html')

    # Sort objects alphabetically by label for consistent output
    sorted_tracked_objects = dict(sorted(tracked_objects.items()))

    html_content = template.render(
        video_file=video_blob.name,
        tracked_objects=sorted_tracked_objects
    )

    report_filename = 'report.html'
    with open(report_filename, 'w') as f:
        f.write(html_content)

    print(f"\nSuccessfully generated report: {report_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates an HTML report or diagnoses JSON structure from a Google Video Intelligence analysis file."
    )
    parser.add_argument(
        "gcs_uri",
        help='The GCS URI of the JSON analysis file (e.g., "gs://your-bucket/your-video.json").',
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Your Google Cloud project ID.",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Run in diagnostic mode. Prints the JSON structure and exits.",
    )
    args = parser.parse_args()
    generate_report(args.gcs_uri, args.project_id, args.diagnose)