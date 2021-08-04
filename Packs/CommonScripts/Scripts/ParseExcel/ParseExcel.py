import demistomock as demisto  # noqa: F401
import xlrd
from CommonServerPython import *  # noqa: F401

fileEntryID = demisto.args()['entryId']

res = demisto.executeCommand('getFilePath', {'id': fileEntryID})

filePath = res[0]['Contents']['path']

workbook = xlrd.open_workbook(filePath, on_demand=True)
sheet_names = workbook.sheet_names()
sheets = []
context = {}

for sheetnum in range(workbook.nsheets):
    worksheet = workbook.sheet_by_index(sheetnum)
    first_row = []
    for col in range(worksheet.ncols):
        first_row.append(worksheet.cell_value(0, col))
    data = []
    for row in range(1, worksheet.nrows):
        elm = {}
        for col in range(worksheet.ncols):
            elm[first_row[col]] = worksheet.cell_value(row, col)
        data.append(elm)
    sheets.append(data)
    context["ParseExcel"] = sheets
    demisto.results(
        {'Type': entryTypes['note'],
         'Contents': data,
         'ContentsFormat': formats['json'],
         'HumanReadable': tblToMd(sheet_names[sheetnum], data, first_row),
         'EntryContext': context
         })
