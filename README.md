# Video Analysis and Reporting Scripts

This repository contains a suite of Python scripts to analyze videos for object tracking using the Google Cloud Video Intelligence API and generate an interactive HTML report. The workflow is orchestrated to start from an FCPXML file, automatically finding and processing tagged video assets.

## Features

-   **FCPXML Parsing:** The main script can parse an `.fcpxml` file from Google Cloud Storage (GCS) to find video assets tagged with specific keywords (e.g., "decor", "guest").
-   **Automated Video Analysis:** The `video_indexer.py` script processes video files from GCS and uses the Video Intelligence API to perform object tracking.
-   **Shot Classification:** The `generate_report.py` script analyzes tracking data to classify shots containing people as "Close-up," "Medium," or "Wide."
-   **Consolidated Interactive Reports:** The workflow generates a single, self-contained `report.html` file with interactive, scrubbable thumbnails for all analyzed videos.

## Prerequisites

-   A Google Cloud Platform (GCP) project with billing enabled.
-   The Video Intelligence API enabled in your GCP project.
-   The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed on your machine.
-   Permissions to access the Video Intelligence API (e.g., the "Video Intelligence User" role) and read/write access to your GCS bucket.

## Setup

1.  **Clone this repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Set up authentication:**
    - Authenticate using Application Default Credentials (ADC). This is a secure method that does not require managing service account keys.
      ```bash
      gcloud auth application-default login
      ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Workflow

The entire process is automated by the `process_fcpxml.py` script. It handles finding the FCPXML file, identifying the correct videos, analyzing them, and generating a single report.

### Run the Automated Workflow

Run the `process_fcpxml.py` script and provide your Google Cloud project ID. You can also specify the GCS bucket and FCPXML filename if they differ from the defaults.

The script will perform all the necessary steps and create a single `report.html` file in your local directory.

#### Example

```bash
# Run with default bucket ("kaon123_bucket") and file ("Jennifer.fcpxml")
python process_fcpxml.py --project-id your-gcp-project-id

# Specify a different bucket or filename
python process_fcpxml.py --project-id your-gcp-project-id --bucket-name my-other-bucket --fcpxml-name project_file.fcpxml
```

You can open the generated `report.html` file in any web browser to view the visual summary of the analysis for all processed videos.

### Troubleshooting: Blank or Empty Reports

If your `report.html` file is blank or shows a "No Objects Detected" message, it could be due to a few reasons:
1.  The FCPXML file does not contain any video assets with the keywords "decor" or "guest".
2.  The video analysis with the Video Intelligence API did not detect any objects.

The `process_fcpxml.py` script will print the GCS URIs of the JSON analysis files it creates. If you suspect an issue with the data processing, you can run the `generate_report.py` script in diagnostic mode on one of these URIs.

```bash
# The URI will be printed in the output of the main script
python generate_report.py gs://your-bucket-name/your-video.json --project-id your-gcp-project-id --diagnose
```

This will save a `diagnostic_output.json` file locally, which you can inspect to see the raw data received from the Video Intelligence API.