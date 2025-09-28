# Video Analysis and Reporting Scripts

This repository contains a suite of Python scripts to analyze videos for object tracking using the Google Cloud Video Intelligence API and generate an interactive HTML report with shot type classification.

## Features

-   **Video Analysis:** The `video_indexer.py` script processes a video file from Google Cloud Storage (GCS) and uses the Video Intelligence API to perform object tracking.
-   **Shot Classification:** The `generate_report.py` script analyzes the tracking data to classify shots containing people as "Close-up," "Medium," or "Wide" shots based on the person's size relative to the frame.
-   **Interactive Reports:** The report generator creates a self-contained `report.html` file with interactive thumbnails. You can hover your mouse over the thumbnails to scrub through a preview of the video segment.

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

The process is two steps: first you analyze the video to generate a JSON data file, then you generate the HTML report from that data file.

### Step 1: Analyze the Video

Run the `video_indexer.py` script to perform object tracking on a video. You must provide the GCS URI of the video file and your Google Cloud project ID.

The script will save the full JSON response containing the object tracking data to the same GCS bucket, replacing the video's file extension with `.json`.

#### Example

```bash
python video_indexer.py gs://your-bucket-name/your-video.mp4 --project-id your-gcp-project-id
```

### Step 2: Generate the Visual Report

Once the analysis is complete and the `.json` file is in your GCS bucket, run the `generate_report.py` script. Provide the GCS URI of the `.json` file created in the previous step.

The script will download the necessary files, classify the shots, extract frame sequences for the interactive thumbnails, and create a single `report.html` file in your local directory.

#### Example

```bash
python generate_report.py gs://your-bucket-name/your-video.json --project-id your-gcp-project-id
```

You can open the generated `report.html` file in any web browser to view the visual summary of the analysis, including the shot type for each detected person.
