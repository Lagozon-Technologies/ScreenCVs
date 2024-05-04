import os

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

def get_blob_service_client(connect_str: str):
    # Use DefaultAzureCredential to fetch credentials from the environment
    
    # Create the BlobServiceClient object
    
    # Create the BlobServiceClient object
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    return blob_service_client


def upload_folder_to_blob(blob_service_client: BlobServiceClient, container_name: str, files: list):
    # Ensure the container exists and create if necessary
    container_client = blob_service_client.get_container_client(container_name)

    # Upload each file to Azure Blob Storage
    for file in files:
        # Extract file name and contents from the file object
        file_name = file.filename
        file_contents = file.read()

        # Upload the file to Azure Blob Storage
        blob_client = container_client.get_blob_client(file_name)
        print(f"Uploading {file_name} to blob storage...")
        blob_client.upload_blob(file_contents, overwrite=True)

def get_blob_folders(blob_service_client, container_name):
    folders = []
    container_client = blob_service_client.get_container_client(container_name)
    for file in container_client.walk_blobs():
        folders.append(file.name)
    return folders