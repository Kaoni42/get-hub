import argparse
import base64
import json
import os
import tempfile

import cv2
from google.cloud import storage
from jinja2 import Environment, FileSystemLoader


def generate_report(gcs_uri: str, project_id: str):
    """
    Generates an HTML report from a Video Intelligence JSON analysis file.

    Args:
        gcs_uri: The GCS URI of the JSON analysis file.
        project_id: The Google Cloud project ID.
    """
    print(f"Starting report generation for {gcs_uri}")

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
    json_data = json.loads(json_blob.download_as_string())

    # Determine video file name
    video_blob_name, _ = os.path.splitext(json_blob_name)
    possible_video_extensions = ['.mp4', '.mov', '.avi', '.mpg']
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

    # --- Process Video and Generate Thumbnails ---
    print("Processing video to generate thumbnails...")
    cap = cv2.VideoCapture(video_path)
    results_data = []
    NUM_FRAMES_PER_SEGMENT = 15  # Number of frames for the scrub sequence

    if not cap.isOpened():
        raise IOError(f"Could not open video file: {video_path}")

    # Correctly and robustly parse the JSON to find all label annotations.
    # Based on the user's diagnostic output, the data is in `shotLabelAnnotations`.
    all_annotations = []
    if 'annotationResults' in json_data and json_data.get('annotationResults'):
        for result in json_data['annotationResults']:
            if 'shotLabelAnnotations' in result and result.get('shotLabelAnnotations'):
                all_annotations.extend(result['shotLabelAnnotations'])

    print(f"Found a total of {len(all_annotations)} label annotations to process.")

    for annotation in all_annotations:
        label = annotation.get('entity', {}).get('description', 'N/A')
        thumbnails_list = []
        start_time, end_time, confidence = -1, -1, 0

        if 'segments' in annotation and annotation.get('segments'):
            segment = annotation['segments'][0]
            confidence = segment.get('confidence', 0)
            segment_data = segment.get('segment', {})
            start_time_str = segment_data.get('startTimeOffset', '0s')
            end_time_str = segment_data.get('endTimeOffset', '0s')
            start_time = float(start_time_str.rstrip('s'))
            end_time = float(end_time_str.rstrip('s'))

            duration = end_time - start_time

            if duration > 0.1:
                interval = duration / NUM_FRAMES_PER_SEGMENT
                for i in range(NUM_FRAMES_PER_SEGMENT):
                    time_pos_ms = (start_time + (i * interval)) * 1000
                    cap.set(cv2.CAP_PROP_POS_MSEC, time_pos_ms)
                    success, frame = cap.read()
                    if success:
                        _, buffer = cv2.imencode('.jpg', frame)
                        thumbnails_list.append(base64.b64encode(buffer).decode('utf-8'))
            else:
                cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)
                success, frame = cap.read()
                if success:
                    _, buffer = cv2.imencode('.jpg', frame)
                    thumbnails_list.append(base64.b64encode(buffer).decode('utf-8'))
        else:
            # Handle labels with no segments (video-level)
            cap.set(cv2.CAP_PROP_POS_MSEC, 1000) # Default to 1s mark
            success, frame = cap.read()
            if success:
                _, buffer = cv2.imencode('.jpg', frame)
                thumbnails_list.append(base64.b64encode(buffer).decode('utf-8'))

        if not thumbnails_list:
            thumbnails_list.append("")

        results_data.append({
            'label': label,
            'start_time': start_time,
            'end_time': end_time,
            'confidence': confidence,
            'thumbnails': thumbnails_list
        })

    cap.release()
    os.remove(video_path)
    print("Finished generating thumbnails.")

    # --- Render HTML Report ---
    print("Rendering HTML report...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(script_dir))
    template = env.get_template('template.html')

    html_content = template.render(
        video_file=video_blob.name,
        results=results_data
    )

    report_filename = 'report.html'
    with open(report_filename, 'w') as f:
        f.write(html_content)

    print(f"\nSuccessfully generated report: {report_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generates an HTML report with thumbnails from a Google Video Intelligence analysis file."
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
    args = parser.parse_args()
    generate_report(args.gcs_uri, args.project_id)