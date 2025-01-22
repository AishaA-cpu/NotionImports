import os
from notion_client import Client
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from dotenv import load_dotenv


def get_google_drive_service():
    """
    get or create Google Drive service
    Returns: Google Drive service
    """
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)


def get_files_from_folder(service, folder_id):
    """
    get all files in the specified folder id from the service
    :param service: Google Drive service object
    :param folder_id:string
    :return: a list of dictionaries containing the file information
    """
    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/pdf'",
        fields="files(id, name, webViewLink)"
    ).execute()

    return results.get('files', [])


def delete_existing_database(notion, page_id, database_name="Reading List"):
    """
    delete existing notion page database with the specified name
    """
    blocks = notion.blocks.children.list(block_id=page_id)
    for block in blocks["results"]:
        if block["type"] == "child_database":
            try:
                db = notion.databases.retrieve(database_id=block["id"])
                if db["title"][0]["text"]["content"] == database_name:
                    notion.blocks.update(block_id=block["id"], archived=True)
                    print("successfully archived block id", block["id"])
            except Exception as e:
                print(f"Error checking database: {str(e)}")



def import_pdfs_to_notion(notion_api_key, page_id, folder_id):
    """
    import pdfs into notion
    :param notion_api_key:
    :param page_id:
    :param folder_id:
    :return:
    """

    notion = Client(auth=notion_api_key)
    drive_service = get_google_drive_service()
    pdf_files = get_files_from_folder(drive_service, folder_id)
    delete_existing_database(notion, page_id)

    if not pdf_files:
        print("no pdf files found in the specified google drives folder")
        return
    database = notion.databases.create(
        parent={"type": "page_id", "page_id": page_id},
        title=[{"type": "text", "text": {"content": "Reading List"}}],
        properties={
            "Name": {"title": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "To Read", "color": "red"},
                        {"name": "Reading", "color": "yellow"},
                        {"name": "Read", "color": "green"}
                    ]
                }
            },
            "Link": {"url": {}}
        }
    )
    for pdf in pdf_files:
        try:
            new_page = notion.pages.create(
                parent={"database_id": database["id"]},
                properties={
                    "Name": {"title": [{"text": {"content": pdf['name'].replace('.pdf', '')}}]},
                    "Status": {"select": {"name": "To Read"}},
                    "Link": {"url": pdf["webViewLink"]}
                },
                children=[
                    {
                        "type": "embed",
                        "embed": {
                            "url": pdf["webViewLink"]
                        }
                    }
                ]
            )
            print("Successfully created a page for:", pdf["name"])
        except Exception as e:
            print(f"Error creating page for book {str(e)} {pdf['name']}")


if __name__ == "__main__":
    load_dotenv()
    NOTION_API_KEY = os.getenv("NOTION_KEY")
    NOTION_PAGE_ID = os.getenv("NOTION_PAGE_ID")
    DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

    try:
        import_pdfs_to_notion(NOTION_API_KEY, NOTION_PAGE_ID, DRIVE_FOLDER_ID)
        print("successfully imported books to notion")
    except Exception as e:
        print(f"Error importing books to notion {str(e)}")
