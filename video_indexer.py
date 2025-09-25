import argparse
import json

from google.api_core.client_options import ClientOptions
from google.cloud import videointelligence
from google.protobuf.json_format import MessageToJson


def analyze_labels(gcs_uri: str, project_id: str, output_file: str = None) -> None:
    """
    Analyzes labels in a video stored in Google Cloud Storage.

    Args:
        gcs_uri: The Google Cloud Storage URI of the video file to analyze.
                 Must be in the format "gs://<bucket-name>/<object-name>".
        project_id: The Google Cloud project ID to use for billing and quotas.
        output_file: Optional. Path to save the full JSON API response.
    """
    # When using Application Default Credentials, the project ID must be provided
    # to specify which project to use for billing and quotas.
    # For more information on authentication, see:
    # https://cloud.google.com/docs/authentication/production
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

    if output_file:
        # The result is a protobuf object. Convert it to a JSON string.
        json_response = MessageToJson(result)
        with open(output_file, "w") as f:
            f.write(json_response)
        print(f"\nFull API response saved to {output_file}")

    # Get the first result, since we are only processing one video.
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
        description="Analyzes labels in a video using the Google Cloud Video Intelligence API."
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
    parser.add_argument(
        "--output-file",
        help="Optional. Path to save the full JSON API response.",
    )
    args = parser.parse_args()
    analyze_labels(args.gcs_uri, args.project_id, args.output_file)