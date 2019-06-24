import demistomock as demisto
from CommonServerPython import *
from CommonServerUserPython import *

''' IMPORTS '''
import traceback
import json
import requests
from datetime import datetime as dt

# Disable insecure warnings
requests.packages.urllib3.disable_warnings()

''' GLOBALS/PARAMS '''

# Remove trailing slash to prevent wrong URL path to service
API_URL = demisto.params()['url'].rstrip('/')

# Should we use SSL
USE_SSL = not demisto.params().get('insecure', False)

# Remove proxy if not set to true in params
if not demisto.params().get('proxy'):
    del os.environ['HTTP_PROXY']
    del os.environ['HTTPS_PROXY']
    del os.environ['http_proxy']
    del os.environ['https_proxy']

THRESHOLD = int(demisto.params().get('threshold', 1))

COMPROMISED_IS_MALICIOUS = demisto.params().get('compromised_is_malicious', False)

# Headers to be sent in requests
HEADERS = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'application/json'
}

''' HELPER FUNCTIONS '''


def http_request(method, command, data=None):
    url = f'{API_URL}/{command}/'
    demisto.info(f'{method} {url}')
    res = requests.request(method,
                           url,
                           verify=USE_SSL,
                           data=data,
                           headers=HEADERS)

    if res.status_code != 200:
        raise Exception(f'Error in API call {url} [{res.status_code}] - {res.reason}')

    return res


def query_url_information(url):
    return http_request('POST',
                        'url',
                        f'url={url}')


def query_host_information(host):
    return http_request('POST',
                        'https://urlhaus-api.abuse.ch/v1/host/',  # disable-secrets-detection
                        f'host={host}')


def query_payload_information(hash_type, hash):
    return http_request('POST',
                        'https://urlhaus-api.abuse.ch/v1/payload/',  # disable-secrets-detection
                        f'{hash_type}_hash={hash}')


def query_tag_information(tag):
    return http_request('POST',
                        'https://urlhaus-api.abuse.ch/v1/tag/',  # disable-secrets-detection
                        f'tag={tag}')


def query_signature_information(signature):
    return http_request('POST',
                        'https://urlhaus-api.abuse.ch/v1/signature/',  # disable-secrets-detection
                        f'signature={signature}')


def download_malware_sample(sha256, dest):
    res = requests.get(f'https://urlhaus-api.abuse.ch/v1/download/{sha256}/')  # disable-secrets-detection
    with open(dest, 'wb') as malware_sample:
        malware_sample.write(res.content)


def item_to_incident(item):
    incident = {}
    # Incident Title
    incident['name'] = 'Example Incident: ' + item.get('name')
    # Incident occurrence time, usually item creation date in service
    incident['occurred'] = item.get('createdDate')
    # The raw response from the service, providing full info regarding the item
    incident['rawJSON'] = json.dumps(item)
    return incident


''' COMMANDS + REQUESTS FUNCTIONS '''


def test_module():
    """
    Performs basic get request to get item samples
    """
    http_request('POST', 'url')


def url_command():
    url = demisto.args().get('url')
    try:
        url_information = query_url_information(url).json()

        ec = {
            'URL': {
                'Data': url
            },
            'DBotScore': {
                'Type': 'url',
                'Vendor': 'URLhaus',
                'Indicator': url
            }
        }

        if url_information['query_status'] == 'ok':
            # URLHaus output
            date_added = dt.strptime(url_information.get('date_added', '1970-01-01 00:00:00 UTC'),
                                     '%Y-%m-%d %H:%M:%S UTC').strftime('%Y-%m-%dT%H:%M:%S')
            urlhaus_data = {
                'ID': url_information.get('id', ''),
                'Status': url_information.get('url_status', ''),
                'Host': url_information.get('host', ''),
                'DateAdded': date_added,
                'Threat': url_information.get('threat', ''),
                'Blacklist': url_information.get('blacklists', {}),
                'Tags': url_information.get('tags', [])
            }

            payloads = []
            for payload in url_information.get('payloads', []):
                payloads.append({
                    'Name': payload.get('filename', 'unknown'),
                    'Type': payload.get('file_type', ''),
                    'MD5': payload.get('response_md5', ''),
                    'VT': payload.get('virustotal', None)
                })

            urlhaus_data['Payloads'] = payloads

            # DBot score calculation
            blacklist_appearances = []
            for blacklist, status in url_information.get('blacklists', {}).items():
                if blacklist == 'spamhaus_dbl':
                    if status.endswith('domain') or (status.startswith('abused') and COMPROMISED_IS_MALICIOUS):
                        blacklist_appearances.append((blacklist, status))
                elif status == 'listed':
                    blacklist_appearances.append((blacklist,))

            if len(blacklist_appearances) >= THRESHOLD:
                ec['DBotScore']['Score'] = 3
                ec['URL']['Malicious'] = {
                    'Vendor': 'URLhaus'
                }

                description = ''
                for appearance in blacklist_appearances:
                    if len(appearance) == 1:
                        description += f'Listed in {appearance[0]}. '
                    elif len(appearance) == 2:
                        description += f'Listed as {appearance[1]} in {appearance[0]}. '
                    else:
                        raise Exception('Unknown blacklist format in the response')

                ec['URL']['Malicious']['Description'] = description
            elif len(blacklist_appearances) > 0:
                ec['DBotScore']['Score'] = 2
            else:
                ec['DBotScore']['Score'] = 1

            ec['URLhaus.URL(val.ID && val.ID === obj.ID)'] = urlhaus_data

            human_readable = f'## URLhaus reputation for {url}\n' \
                f'URLhaus link: {url_information.get("urlhaus_reference", "None")}\n' \
                f'Threat: {url_information.get("threat", "")}\n' \
                f'Date added: {date_added}'

            demisto.results({
                'Type': entryTypes['note'],
                'ContentsFormat': formats['json'],
                'Contents': url_information,
                'HumanReadable': human_readable,
                'HumanReadableFormat': formats['markdown'],
                'EntryContext': ec
            })
        elif url_information['query_status'] == 'no_results':
            ec['DBotScore']['Score'] = 0

            human_readable = f'## URLhaus reputation for {url}\n' \
                f'No results!'

            demisto.results({
                'Type': entryTypes['note'],
                'ContentsFormat': formats['json'],
                'Contents': url_information,
                'HumanReadable': human_readable,
                'HumanReadableFormat': formats['markdown'],
                'EntryContext': ec
            })
        elif url_information['query_status'] == 'invalid_url':
            human_readable = f'## URLhaus reputation for {url}\n' \
                f'Invalid URL!'

            demisto.results({
                'Type': entryTypes['note'],
                'ContentsFormat': formats['json'],
                'Contents': url_information,
                'HumanReadable': human_readable,
                'HumanReadableFormat': formats['markdown'],
                'EntryContext': ec
            })
        else:
            demisto.results({
                'Type': entryTypes['error'],
                'ContentsFormat': formats['text'],
                'Contents': f'Query results = {url_information["query_status"]}'
            })

    except Exception:
        demisto.debug(traceback.format_exc())
        return_error('Failed getting url data, please verify the arguments and parameters')

# def get_items_command():
#     """
#     Gets details about a items using IDs or some other filters
#     """
#     # Init main vars
#     headers = []
#     contents = []
#     context = {}
#     context_entries = []
#     title = ''
#     # Get arguments from user
#     item_ids = argToList(demisto.args().get('item_ids', []))
#     is_active = bool(strtobool(demisto.args().get('is_active', 'false')))
#     limit = int(demisto.args().get('limit', 10))
#     # Make request and get raw response
#     items = get_items_request(item_ids, is_active)
#     # Parse response into context & content entries
#     if items:
#         if limit:
#             items = items[:limit]
#         title = 'Example - Getting Items Details'
#
#         for item in items:
#             contents.append({
#                 'ID': item.get('id'),
#                 'Description': item.get('description'),
#                 'Name': item.get('name'),
#                 'Created Date': item.get('createdDate')
#             })
#             context_entries.append({
#                 'ID': item.get('id'),
#                 'Description': item.get('description'),
#                 'Name': item.get('name'),
#                 'CreatedDate': item.get('createdDate')
#             })
#
#         context['Example.Item(val.ID && val.ID === obj.ID)'] = context_entries
#
#     demisto.results({
#         'Type': entryTypes['note'],
#         'ContentsFormat': formats['json'],
#         'Contents': contents,
#         'ReadableContentsFormat': formats['markdown'],
#         'HumanReadable': tableToMarkdown(title, contents, removeNull=True),
#         'EntryContext': context
#     })
#
#
# def get_items_request(item_ids, is_active):
#     # The service endpoint to request from
#     endpoint_url = 'items'
#     # Dictionary of params for the request
#     params = {
#         'ids': item_ids,
#         'isActive': is_active
#     }
#     # Send a request using our http_request wrapper
#     response = http_request('GET', endpoint_url, params)
#     # Check if response contains errors
#     if response.get('errors'):
#         return_error(response.get('errors'))
#     # Check if response contains any data to parse
#     if 'data' in response:
#         return response.get('data')
#     # If neither was found, return back empty results
#     return {}
#
#
# def fetch_incidents():
#     last_run = demisto.getLastRun()
#     # Get the last fetch time, if exists
#     last_fetch = last_run.get('time')
#
#     # Handle first time fetch, fetch incidents retroactively
#     if last_fetch is None:
#         last_fetch, _ = parse_date_range(FETCH_TIME, to_timestamp=True)
#
#     incidents = []
#     items = get_items_request()
#     for item in items:
#         incident = item_to_incident(item)
#         incident_date = date_to_timestamp(incident['occurred'], '%Y-%m-%dT%H:%M:%S.%fZ')
#         # Update last run and add incident if the incident is newer than last fetch
#         if incident_date > last_fetch:
#             last_fetch = incident_date
#             incidents.append(incident)
#
#     demisto.setLastRun({'time' : last_fetch})
#     demisto.incidents(incidents)


''' COMMANDS MANAGER / SWITCH PANEL '''

LOG('Command being called is %s' % (demisto.command()))

try:
    if demisto.command() == 'test-module':
        # This is the call made when pressing the integration test button.
        test_module()
        demisto.results('ok')
    elif demisto.command() == 'url':
        url_command()

# Log exceptions
except Exception as e:
    LOG(str(e))
    LOG.print_log()
    raise
