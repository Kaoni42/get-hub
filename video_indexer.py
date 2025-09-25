import argparse
import os

from google.api_core.client_options import ClientOptions
from google.cloud import videointelligence
from google.cloud import storage


def analyze_labels(gcs_uri: str, project_id: str) -> None:
    """
    Analyzes labels in a video and saves the results to the same GCS bucket.

    Args:
        gcs_uri: The Google Cloud Storage URI of the video file to analyze.
                 Must be in the format "gs://<bucket-name>/<object-name>".
        project_id: The Google Cloud project ID to use for billing and quotas.
    """
    # When using Application Default Credentials, the project ID must be provided
    # to specify which project to use for billing and quotas.
    client_options = ClientOptions(quota_project_id=project_id)
    video_client = videointelligence.VideoIntelligenceServiceClient(
        client_options=client_options
    )

    features = [videointelligence.Feature.LABEL_DETECTION]

    operation = video_client.annotate_video(
        request={"features": features, "input_uri": gcs_uri}
    )

    print(f"\nProcessing video for label analysis: {gcs_uri}")
    print("This may take a few minutes depending on the video length.")

    result = operation.result(timeout=300)

    print("\nFinished processing.")

    # The `result` object is a special proxy object. We need to access
    # the underlying `_pb` (protobuf) object to serialize it correctly.
    json_response = videointelligence.AnnotateVideoResponse.to_json(result._pb)

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
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    output_blob = bucket.blob(output_blob_name)
    output_blob.upload_from_string(json_response, content_type="application/json")

    output_gcs_uri = f"gs://{bucket_name}/{output_blob_name}"
    print(f"\nFull API response saved to {output_gcs_uri}")

    # Get the first result, since we are only processing one video.
    if result.annotation_results:
        segment_labels = result.annotation_results[0].segment_label_annotations
        for i, segment_label in enumerate(segment_labels):
            print(f"Video label description: {segment_label.entity.description}")
            for category_entity in segment_label.category_entities:
                print(f"\tLabel category description: {category_entity.description}")

            for i, segment in enumerate(segment_label.segments):
                start_time = (
                    segment.segment.start_time_offset.seconds
                    + segment.segment.start_time_offset.microseconds / 1e6
                )
                end_time = (
                    segment.segment.end_time_offset.seconds
                    + segment.segment.end_time_offset.microseconds / 1e6
                )
                positions = f"{start_time}s to {end_time}s"
                confidence = segment.confidence
                print(f"\tSegment {i}: {positions} (confidence: {confidence})")
            print("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyzes labels in a video using the Google Cloud Video Intelligence API and saves the results to the same GCS bucket."
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
    analyze_labels(args.gcs_uri, args.project_id)