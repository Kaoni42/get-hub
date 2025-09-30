import argparse
import os

from google.api_core.client_options import ClientOptions
from google.cloud import videointelligence
from google.cloud import storage


def analyze_video(gcs_uri: str, project_id: str):
    """
    Analyzes a video for object tracking and saves the results to GCS.

    Args:
        gcs_uri: The Google Cloud Storage URI of the video file to analyze.
        project_id: The Google Cloud project ID for billing and quotas.
    """
    client_options = ClientOptions(quota_project_id=project_id)
    video_client = videointelligence.VideoIntelligenceServiceClient(
        client_options=client_options
    )

    # Change the feature to OBJECT_TRACKING
    features = [videointelligence.Feature.OBJECT_TRACKING]

    print(f"\nProcessing video for object tracking: {gcs_uri}")
    operation = video_client.annotate_video(
        request={"features": features, "input_uri": gcs_uri}
    )

    print("This may take a few minutes depending on the video length...")
    result = operation.result(timeout=900) # Increased timeout for potentially longer analysis
    print("\nFinished processing.")

    json_response = videointelligence.AnnotateVideoResponse.to_json(result)

    # Parse the GCS URI to get bucket and object path.
    if not gcs_uri.startswith("gs://"):
        raise ValueError("Invalid GCS URI. Must start with 'gs://'")

    path_parts = gcs_uri[5:].split("/", 1)
    bucket_name = path_parts[0]
    blob_name = path_parts[1] if len(path_parts) > 1 else ""

    # Create the output blob name by replacing the video extension with .json
    output_blob_name, _ = os.path.splitext(blob_name)
    output_blob_name += ".json"

    # Upload the JSON to the same GCS bucket.
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    output_blob = bucket.blob(output_blob_name)
    output_blob.upload_from_string(json_response, content_type="application/json")

    output_gcs_uri = f"gs://{bucket_name}/{output_blob_name}"
    print(f"\nFull API response with object tracking data saved to {output_gcs_uri}")
    return output_gcs_uri


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyzes a video for object tracking and saves the results to the same GCS bucket."
    )
    parser.add_argument(
        "gcs_uri",
        help='The Google Cloud Storage URI of the video file to analyze (e.g., "gs://your-bucket/your-video.mp4").',
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Your Google Cloud project ID to use for billing and API quotas.",
    )
    args = parser.parse_args()
    analyze_video(args.gcs_uri, args.project_id)