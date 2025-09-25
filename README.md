# Google Cloud Video Intelligence API Script

This repository contains a Python script to analyze videos using the Google Cloud Video Intelligence API.

## Prerequisites

Before you can run the script, you need to have the following:

- A Google Cloud Platform (GCP) project with billing enabled.
- The Video Intelligence API enabled in your GCP project.
- The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed on your machine.
- Permissions to access the Video Intelligence API (e.g., the "Video Intelligence User" role).

### Setup Instructions

1.  **Create or select a GCP project:**
    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Create a new project or select an existing one.

2.  **Enable the Video Intelligence API:**
    - In the Cloud Console, navigate to the "APIs & Services" > "Library".
    - Search for "Video Intelligence API" and enable it for your project.

3.  **Set up authentication:**
    - Authenticate using Application Default Credentials (ADC). This method is secure and does not require managing service account keys. It will open a browser window for you to log in to your Google account.
      ```bash
      gcloud auth application-default login
      ```
    - The Python script will automatically detect and use these credentials. There is no need to set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

## Installation

1.  Clone this repository:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

To analyze a video, run the `video_indexer.py` script. You must provide the Google Cloud Storage (GCS) URI of the video file and your Google Cloud project ID.

### Example

```bash
python video_indexer.py gs://your-bucket-name/your-video.mp4 --project-id your-gcp-project-id
```

-   Replace `gs://your-bucket-name/your-video.mp4` with the GCS path to your video file.
-   Replace `your-gcp-project-id` with your Google Cloud project ID.

The script will then process the video and print the detected labels along with their timestamps.