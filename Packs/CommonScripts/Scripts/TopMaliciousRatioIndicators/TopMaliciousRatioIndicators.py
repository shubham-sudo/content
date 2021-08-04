import json
import random
from datetime import datetime, timedelta

import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401


def select_indicator_columns(indicator):
    display_indicator = {}
    display_indicator['ID'] = indicator['id']
    display_indicator['Type'] = indicator['indicator_type']
    display_indicator['Malicious Ratio'] = '%.2f' % float(indicator['maliciousRatio'])
    display_indicator['Value'] = indicator['value']
    display_indicator['Last Seen'] = indicator['lastSeen']
    return display_indicator


def dedup_by_value(indicators_list):
    exist_values = set()
    result = []
    for e in indicators_list:
        value = e['value']
        if value not in exist_values:
            exist_values.add(value)
            result.append(e)
    return result


MAX_INDICATORS = int(demisto.args()['maxNumberOfIndicators'])
MIN_NUMBER_OF_INVS = int(demisto.args()['minimumNumberOfInvs'])
MAX_RESULTS = int(demisto.args()['maximumNumberOfResults'])
from_date = demisto.args().get('from', '"30 days ago"')
res = demisto.executeCommand("findIndicators", {'query': 'lastSeen:>=%s' % from_date, 'size': MAX_INDICATORS})
indicators = res[0]['Contents']
indicators = [i for i in indicators if len(i.get('investigationIDs') or []) >= MIN_NUMBER_OF_INVS]
indicators_map = {}
for i in indicators:
    indicators_map[i['id']] = i
res = demisto.executeCommand("maliciousRatio", {'id': ",".join(indicators_map.keys())})
malicious_ratio_result = res[0]['Contents']
for mr in malicious_ratio_result:
    indicators_map[mr['indicatorId']]['maliciousRatio'] = mr['maliciousRatio']
    indicators_map[mr['indicatorId']]['from_date'] = from_date
sorted_indicators = sorted(indicators_map.values(), key=lambda x: x['maliciousRatio'], reverse=True)
sorted_indicators = [x for x in sorted_indicators if x['maliciousRatio'] > 0]
sorted_indicators = dedup_by_value(sorted_indicators)
sorted_indicators = sorted_indicators[:MAX_RESULTS]
sorted_indicators = map(select_indicator_columns, sorted_indicators)
widget_table = json.dumps({"total": len(sorted_indicators), "data": sorted_indicators})
demisto.results({
    'Type': entryTypes['note'],
    'Contents': widget_table,
    'ContentsFormat': formats['text'],
    'ReadableContentsFormat': formats['markdown'],
    'HumanReadable': tableToMarkdown('Top Malicious Ratio Indicators', sorted_indicators, headers=['ID', 'Malicious Ratio', 'Type', 'Value', 'Last Seen'])
})
