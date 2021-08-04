import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

res = []
errEntry = {
    "Type": entryTypes["error"],
    "ContentsFormat": formats["text"],
    "Contents": ""
}

try:
    cmd_res = demisto.executeCommand('getFilePath', {'id': demisto.args()['entryID']})
    file_res = cmd_res[0]
    if isError(file_res):
        file_res["Contents"] = "Error fetching entryID: " + file_res["Contents"]
        res = file_res
    else:
        file_path = file_res['Contents']['path']
        document = Document(file_path)
        file_data = '\n'.join([para.text for para in document.paragraphs])
        file_name = file_res['Contents']['name']
        output_file_name = file_name[0:file_name.rfind('.')] + '.txt'
        res = fileResult(output_file_name, file_data.encode('utf8'))
except PackageNotFoundError as e:
    errEntry["Contents"] = "Input file is not a valid docx/doc file."
    res = errEntry
except BaseException as e:
    errEntry["Contents"] = "Error occurred while parsing input file.\nException info: " + str(e)
    res = errEntry

demisto.results(res)
