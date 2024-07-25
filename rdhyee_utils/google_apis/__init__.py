from pathlib import Path

from itertools import zip_longest
from collections import OrderedDict

from apiclient import errors

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/sheets.googleapis.com-python-quickstart.json
SCOPES = "https://www.googleapis.com/auth/spreadsheets"

# (2019.02.12) The credentials I'm using right now by default are
# from
# https://console.developers.google.com/apis/credentials/oauthclient/233267314801-umg0d7pdcneu9q2ugf4tvuvjnv0tie5h.apps.googleusercontent.com?project=rdhyee&folder&organizationId

# CLIENT_SECRET_FILE = 'client_secret.json'

CLIENT_SECRET_FILE = Path.home().joinpath(".credentials", "client_secret.json")

SANDBOX_ID = "1McPdxcvGyGKrkuje5N80uIHG-IEW6j9qx-9Dr3GIsL0"


def get_credentials(
    credentials_file_name,
    application_name=None,
    scopes=None,
    client_secret_file=CLIENT_SECRET_FILE,
    flags=None,
    credential_dir=None,
):
    """
    Retrieves or generates credentials for accessing Google APIs.

    Args:
        credentials_file_name (str): The name of the credentials file.
        application_name (str, optional): The name of the application. Defaults to None. (Deprecated)
        scopes (list, optional): The list of scopes for the credentials. Defaults to None.
        client_secret_file (str, optional): The path to the client secret file. Defaults to CLIENT_SECRET_FILE.
        flags (object, optional): The flags object. Defaults to None. (Deprecated)
        credential_dir (str, optional): The directory to store the credentials. Defaults to None.

    Returns:
        google.auth.credentials.Credentials: The credentials for accessing Google APIs.
    """
    if credential_dir is None:
        home_dir = Path.home()
        credential_dir = home_dir.joinpath(".credentials")
    if not credential_dir.exists():
        credential_dir.mkdir(parents=True)
    credential_path = credential_dir.joinpath(credentials_file_name)

    if credential_path.exists():
        credentials = Credentials.from_authorized_user_file(
            credential_path, 
            scopes
        )
    else:
        credentials = None

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file, scopes
            )
            credentials = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(credential_path, "w") as token:
            token.write(credentials.to_json())

    return credentials


def get_service(name, version, credentials):
    """
    Creates and returns a Google API service object.

    Args:
        name (str): The name of the API service.
        version (str): The version of the API service.
        credentials: The credentials object used for authentication.

    Returns:
        object: The Google API service object.

    """
    # Function implementation goes here
    service = build(name, version, credentials=credentials)
    return service


class DriveService(object):
    def __init__(self, credentials, version="v3"):
        self.service = get_service("drive", version, credentials)

    def folders_by_name(self, folder_name):
        page_token = None
        while True:
            q = "name='{}' and mimeType = 'application/vnd.google-apps.folder'".format(
                folder_name
            )
            response = (
                self.service.files()
                .list(
                    q=q,
                    spaces="drive",
                    fields="nextPageToken, files(id, name)",
                    pageToken=page_token,
                )
                .execute()
            )
            for file in response.get("files", []):
                # Process change
                yield file
            page_token = response.get("nextPageToken", None)
            if page_token is None:
                break

    def item_by_name(self, item_name, item_type="file"):
        # https://developers.google.com/drive/v3/web/mime-types

        if not item_type.startswith("application/vnd.google-apps."):
            mimeType = "application/vnd.google-apps.{}".format(item_type)
        else:
            mimeType = item_type

        page_token = None
        while True:
            q = """name='{}' and mimeType = '{}'""".format(item_name, mimeType)
            response = (
                self.service.files()
                .list(
                    q=q,
                    spaces="drive",
                    fields="nextPageToken, files(id, name)",
                    pageToken=page_token,
                )
                .execute()
            )
            for file in response.get("files", []):
                # Process change
                yield file
            page_token = response.get("nextPageToken", None)
            if page_token is None:
                break

    def move_file_to_folder(self, file_id, folder_id):
        # Retrieve the existing parents to remove
        file = self.service.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents"))
        # Move the file to the new folder
        file = (
            self.service.files()
            .update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            )
            .execute()
        )

    def create_folder(self, name):
        file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        file = self.service.files().create(body=file_metadata, fields="id").execute()
        return file

    def delete_file(self, file_id):
        """Permanently delete a file, skipping the trash.

        Args:
        service: Drive API service instance.
        file_id: ID of the file to delete.

        TO DO: allow trashing option:
        https://developers.google.com/drive/v3/reference/files/update
        """
        try:
            self.service.files().delete(fileId=file_id).execute()
        except errors.HttpError as error:
            print("An error occurred: %s" % error)


class SheetsService(object):
    def __init__(self, credentials, version="v4"):
        self.service = get_service("sheets", version, credentials)

    def spreadsheet_metadata(self, spreadsheetId):
        return self.service.spreadsheets().get(spreadsheetId=spreadsheetId).execute()

    # https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets#SpreadsheetProperties

    def create_spreadsheet(self, properties):
        spreadsheet_body = properties

        request = self.service.spreadsheets().create(body=spreadsheet_body)
        response = request.execute()
        return response

    def spreadsheet_properties(self, title, sheet0_title):
        return {
            "properties": {"title": title},
            "sheets": [
                {
                    "properties": {
                        "sheetId": 0,
                        "title": sheet0_title,
                        "index": 0,
                        "sheetType": "GRID",
                        "gridProperties": {"rowCount": 1000, "columnCount": 26},
                    }
                }
            ],
        }

    def add_sheet(self, spreadsheet_id, sheet_title):
        addSheet_props = {"properties": {"title": sheet_title}}

        body = {"requests": [{"addSheet": addSheet_props}]}

        result = (
            self.service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            .execute()
        )

        return result

    def delete_sheet(self, spreadsheet_id, sheetId):
        body = {"requests": [{"deleteSheet": {"sheetId": sheetId}}]}

        result = (
            self.service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            .execute()
        )

        return result

    def get_values(
        self,
        spreadsheetId,
        rangeA1,
        majorDimension="ROWS",
        valueRenderOption="UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING",
    ):
        result = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheetId,
                range=rangeA1,
                majorDimension=majorDimension,
                valueRenderOption=valueRenderOption,
                dateTimeRenderOption=dateTimeRenderOption,
            )
            .execute()
        )
        values = result.get("values", [])

        return values

    def get_values_as_dict(self, sheetId, rangeA1):
        """
        read a sheets range
        assume first row is headers
        """

        values = self.get_values(sheetId, rangeA1)

        headers = values[0]

        for value in values[1:]:
            yield OrderedDict(
                [
                    (header, col)
                    for (header, col) in zip_longest(headers, value, fillvalue="")
                ]
            )


class A1Utils(object):

    """
    adapted from JS version in https://stackoverflow.com/a/21231012
    """

    @staticmethod
    def columnToLetter(column):
        letter = ""

        column = int(column)

        while column > 0:
            temp = (column - 1) % 26
            letter = chr(ord("A") + temp) + letter
            column = (column - temp - 1) // 26

        return letter

    @staticmethod
    def letterToColumn(letter):
        column = 0

        for i, l in enumerate(letter[::-1]):
            column += (ord(l) - ord("A") + 1) * 26**i

        return column

    @staticmethod
    def named_ranges_as_a1(ss_metadata):
        """
        generator for namedranges in A1 notation for
        given google spreadsheet metadata

        https://developers.google.com/sheets/api/samples/ranges

        * 0 based indexing

        ```
        "startColumnIndex": 0,
        "endColumnIndex": 5,  # 1 higher
        "startRowIndex": 3,
        "endRowIndex": 4, # 1 higher
        ```


        `A4:E4`
        """

        sheets_by_id = dict(
            [(sh["properties"]["sheetId"], sh) for sh in ss_metadata["sheets"]]
        )

        for r in ss_metadata["namedRanges"]:
            range_name = r["name"]
            range_ = r["range"]

            sheetId = range_["sheetId"]
            sheet_name = sheets_by_id[sheetId]["properties"]["title"]

            range_start = "{}{}".format(
                A1Utils.columnToLetter(range_["startColumnIndex"] + 1),
                range_["startRowIndex"] + 1,
            )
            range_end = "{}{}".format(
                A1Utils.columnToLetter(range_["endColumnIndex"]), range_["endRowIndex"]
            )

            range_end_formatted = (
                ":{}".format(range_end) if range_start != range_end else ""
            )

            range_a1_notation = "'{}'!{}{}".format(
                sheet_name, range_start, range_end_formatted
            )

            yield (range_name, range_a1_notation)


def apply_locale(n):
    """
    proper? way to deal with comma delimited numbers?
    """
    import locale

    locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
    return locale.atoi(n)
    # 1000000
    locale.atof("1,000,000.53")
