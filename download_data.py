import requests
import os
import base64

REPO = "d-hackmt/8hr-MARATHON"
BRANCH = "main"

FOLDERS = ["DATA/noisy_data", "DATA/true_data"]

def download_folder(folder):
    api_url = f"https://api.github.com/repos/{REPO}/contents/{folder}?ref={BRANCH}"

    response = requests.get(api_url)
    response.raise_for_status()

    for item in response.json():
        if item["type"] == "dir":
            download_folder(item["path"])

        elif item["type"] == "file":
            file_path = item["path"]
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            file_response = requests.get(item["download_url"])
            file_response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(file_response.content)

            print(f"Downloaded: {file_path}")


for folder in FOLDERS:
    download_folder(folder)

print("\nBoth folders downloaded successfully!")