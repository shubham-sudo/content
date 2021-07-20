import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

"""LINE Notify Integration for Cortex XSOAR (aka Demisto)
https://notify-bot.line.me/doc/en/
"""

import requests

''' MAIN FUNCTION '''


def main() -> None:
    api_token = demisto.params().get('apitoken')

    # demisto.debug(f'Command being called is {demisto.command()}')
    try:
        if demisto.command() == 'LINE-send-message':
            # This is for sending LINE notification to specific group
            headers = {
                "Authorization": "Bearer " + api_token,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            linemsg = demisto.args().get('msg')
            payload = {'message': linemsg}
            r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=payload)
            return_results(r)

        elif demisto.command() == 'test-module':
            # This is the call made when pressing the integration Test button.
            # result = test_module(client, first_fetch_timestamp)
            # return_results(result)
            headers = {
                "Authorization": "Bearer " + api_token,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            result = requests.get("https://notify-api.line.me/api/status", headers=headers)
            if '200' not in str(result):
                return_results(result)
            else:
                return_results('ok')

    # Log exceptions and return errors
    except Exception as e:
        demisto.error(traceback.format_exc())  # print the traceback
        return_error(f'Failed to execute {demisto.command()} command.\nError:\n{str(e)}')


''' ENTRY POINT '''

if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
