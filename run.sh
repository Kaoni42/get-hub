#!/bin/bash

# Check if python3 is installed
if ! command -v python3 &> /dev/null
then
    echo "python3 could not be found, please install it."
    exit
fi

# Check if pip is installed
if ! command -v pip &> /dev/null
then
    echo "pip could not be found, please install it."
    exit
fi

# Install dependencies
pip install -r requirements.txt

# Run the script with placeholder credentials
python3 search_fcpxml.py \
  --project_id="jennifer-470222" \
  --bucket_name="jennifer_bucket" \
  --file_name="Jennifer.fcpxml"