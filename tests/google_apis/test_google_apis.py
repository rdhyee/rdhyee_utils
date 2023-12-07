import argparse
import pytest

# add two directories up to sys.path
import sys
from pathlib import Path as P

# add rdhyee_utils to sys.path explicitly
# don't assume that rdhyee_utils is in the PYTHONPATH

p = P(__file__).parents[2]
sys.path.append(str(p))  # noqa: E402

from rdhyee_utils.google_apis import (  # noqa: E402
    get_credentials,
    get_service,
    # get_service_2,
    DriveService,
    SheetsService,
    # A1Utils,
    # apply_locale,
)


flags = argparse.Namespace()


# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/sheets.googleapis.com-python-quickstart.json
SCOPES = "https://www.googleapis.com/auth/spreadsheets"

# (2019.02.12) The credentials I'm using right now by default are
# from
# https://console.developers.google.com/apis/credentials/oauthclient/233267314801-umg0d7pdcneu9q2ugf4tvuvjnv0tie5h.apps.googleusercontent.com?project=rdhyee&folder&organizationId

# CLIENT_SECRET_FILE = 'client_secret.json'

CLIENT_SECRET_FILE = P.home().joinpath(".credentials", "client_secret.json")

SANDBOX_ID = "1McPdxcvGyGKrkuje5N80uIHG-IEW6j9qx-9Dr3GIsL0"


def test_correct_path():
    p = P(__file__).parents[2]
    assert p == P("/Users/raymondyee/C/src/rdhyee_utils")


def test_basic_sheet_scenario():
    """Shows basic usage of the Sheets API.

    Creates a Sheets API service object and prints the names and majors of
    students in a sample spreadsheet:
    https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
    """
    credentials = get_credentials(
        "sheets.googleapis.com-python-quickstart.json",
        "quick start",
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
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
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
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

    drive = DriveService(credentials, version="v3")
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
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
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
