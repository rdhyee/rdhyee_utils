from __future__ import print_function

from pathlib import Path

import httplib2
import os
from itertools import zip_longest
from collections import OrderedDict

import apiclient
from apiclient import errors

from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import argparse

flags = argparse.Namespace()


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
    application_name,
    scopes,
    client_secret_file=CLIENT_SECRET_FILE,
    flags=None,
    credential_dir=None,
):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """

    if credential_dir is None:
        home_dir = os.path.expanduser("~")
        credential_dir = os.path.join(home_dir, ".credentials")
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, credentials_file_name)

    store = Storage(credential_path)
    credentials = store.get()

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[tools.argparser],
    )
    flags = parser.parse_args([])

    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(client_secret_file, scopes)
        flow.user_agent = application_name
        credentials = tools.run_flow(flow, store, flags)
        print("Storing credentials to " + credential_path)

    return credentials


def get_service(name, version, credentials):

    http = credentials.authorize(httplib2.Http())
    service = apiclient.discovery.build(name, version, http=http)
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

        for (i, l) in enumerate(letter[::-1]):
            column += (ord(l) - ord("A") + 1) * 26 ** i

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


def test_hello():

    assert True


def test_basic_sheet_scenario():
    """Shows basic usage of the Sheets API.

    Creates a Sheets API service object and prints the names and majors of
    students in a sample spreadsheet:
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
    """
    credentials = get_credentials(
        "sheets.googleapis.com-python-quickstart.json",
        "quick start",
        "https://www.googleapis.com/auth/spreadsheets",
        client_secret_file=CLIENT_SECRET_FILE,
    )
    service = get_service("sheets", "v4", credentials)

    spreadsheetId = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    rangeName = "Class Data!A2:E"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheetId, range=rangeName)
        .execute()
    )
    values = result.get("values", [])

    assert len(values) == 30


def test_expected_keys_in_spreadsheet_metadata():

    credentials = get_credentials(
        "sheets.googleapis.com-python-quickstart.json",
        "sandbox exploration",
        "https://www.googleapis.com/auth/spreadsheets",
    )
    service = get_service("sheets", "v4", credentials)

    spreadsheetId = SANDBOX_ID

    # how to read sheet names from a given spreadsheet
    result = service.spreadsheets().get(spreadsheetId=spreadsheetId).execute()

    assert set(result.keys()).issubset(
        set(["spreadsheetId", "properties", "sheets", "namedRanges", "spreadsheetUrl"])
    )


def test_drive_service():
    credentials = get_credentials(
        "sheets.googleapis.com-python-quickstart.json",
        "sandbox exploration",
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    drive = DriveService(credentials)
    sheets = SheetsService(credentials)

    # create a folder
    folder = drive.create_folder("Test 2017.08.23")

    # create spreadsheet and move to folder
    ss1 = sheets.create_spreadsheet(
        sheets.spreadsheet_properties("2017.08.23 Sheet", "Sheet 1")
    )
    drive.move_file_to_folder(ss1["spreadsheetId"], folder["id"])

    # add sheet
    sheet2 = sheets.add_sheet(ss1["spreadsheetId"], "Sheet 2")
    # delete sheet
    sheets.delete_sheet(
        ss1["spreadsheetId"], sheet2["replies"][0]["addSheet"]["properties"]["sheetId"]
    )

    # delete folder
    drive.delete_file(folder["id"])


def test_write_query():

    # https://docs.google.com/spreadsheets/d/1McPdxcvGyGKrkuje5N80uIHG-IEW6j9qx-9Dr3GIsL0/edit#gid=0
    spreadsheet_id = SANDBOX_ID
    rangeName = "My Sheet 1!A16"

    credentials = get_credentials(
        "sheets.googleapis.com-python-quickstart.json",
        "sandbox exploration",
        "https://www.googleapis.com/auth/spreadsheets",
    )
    service = get_service("sheets", "v4", credentials)

    values = [
        ['=QUERY(countries, "SELECT sum(B)", -1)'],
        # Additional rows ...
    ]
    body = {"values": values}

    value_input_option = "USER_ENTERED"

    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=rangeName,
            valueInputOption=value_input_option,
            body=body,
        )
        .execute()
    )

    assert result["updatedRows"] == 1

    # read back total

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range="My Sheet 1!A16:A17")
        .execute()
    )

    assert result["values"][1][0] == "3334647600"
