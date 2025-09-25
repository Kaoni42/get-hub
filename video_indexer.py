import argparse

from google.cloud import videointelligence


def analyze_labels(gcs_uri: str) -> None:
    """
    Analyzes labels in a video stored in Google Cloud Storage.

    Args:
        gcs_uri: The Google Cloud Storage URI of the video file to analyze.
                 Must be in the format "gs://<bucket-name>/<object-name>".
    """
    # For more information on authentication, see:
    # https://cloud.google.com/docs/authentication/production
    #
    # The GOOGLE_APPLICATION_CREDENTIALS environment variable should be
    # set to the path of the service account key file.
    video_client = videointelligence.VideoIntelligenceServiceClient()

    features = [videointelligence.Feature.LABEL_DETECTION]

    operation = video_client.annotate_video(
        request={"features": features, "input_uri": gcs_uri}
    )

    print(f"\nProcessing video for label analysis: {gcs_uri}")
    print("This may take a few minutes depending on the video length.")

    result = operation.result(timeout=300)

    print("\nFinished processing.")

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
    args = parser.parse_args()
    analyze_labels(args.gcs_uri)