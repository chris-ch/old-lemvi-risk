import argparse
import logging
import json
import os
from string import Template
from time import sleep
from xml.etree import ElementTree

import requests
from slackclient import SlackClient

from ibrokersflex import parse_flex_result

_SLACK_CHANNEL = 'daily-reports'
_FLEX_QUERY_ID = '251102'
_FLEX_QUERY_SERVER = 'gdcdyn.interactivebrokers.com'
_FLEX_QUERY_PATH = 'Universal/servlet/FlexStatementService.SendRequest'
_FLEX_QUERY_URL_PATTERN = Template('https://$server/$path?t=$token&q=$query_id&v=3')


def create_flex_request_step_1(token):
    flex_params = {
        'server': _FLEX_QUERY_SERVER,
        'path': _FLEX_QUERY_PATH,
        'token': token,
        'query_id': _FLEX_QUERY_ID,
    }
    return _FLEX_QUERY_URL_PATTERN.safe_substitute(flex_params)


def create_flex_request_step_2(url, reference_code, token):
    step_2_pattern = Template('$url?q=$reference_code&t=$token&v=3')
    params = {'url': url, 'reference_code': reference_code, 'token': token}
    return step_2_pattern.safe_substitute(params)


def flex_request(token):
    """
    Requesting IBrokers Flex data
    :param token: 
    :return: 
    """
    request_step_1 = create_flex_request_step_1(token)
    response_1 = requests.get(request_step_1)
    tree_1 = ElementTree.fromstring(response_1.content)
    reference_code = tree_1.findtext('ReferenceCode')
    url = tree_1.findtext('Url')
    request_step_2 = create_flex_request_step_2(url, reference_code, token)
    error_code = '1019'  # goes through the loop at least once
    attempt = 1
    attempt_total = 6
    response_2 = None
    while error_code == '1019' and attempt <= attempt_total:
        params = {'attempt': attempt, 'total': attempt_total}
        logging.info(Template('requesting attempt $attempt / $total').safe_substitute(params))
        response_2 = requests.get(request_step_2)
        tree_2 = ElementTree.fromstring(response_2.content)
        error_code = tree_2.findtext('ErrorCode')
        sleep(5)
        attempt += 1

    accounts = parse_flex_result(response_2.text)
    return accounts


def main(args):
    secrets_file_name = 'secrets.json'
    secrets_file_path = os.path.abspath(secrets_file_name)

    if args.slack_api_token is not None:
        slack_api_token = args.slack_api_token

    else:
        with open(secrets_file_path) as json_data:
            secrets_content = json.load(json_data)
            slack_api_token = secrets_content['slack.api.token']

    attachments = list()
    if args.use_message:
        message_body = args.message_only

    else:
        if args.use_file:
            with open(args.use_file) as content:
                accounts = parse_flex_result(''.join(content.readlines()))

        else:
            if args.ibrokers_flex_token is not None:
                ibrokers_flex_token = args.ibrokers_flex_token

            else:
                with open(secrets_file_path) as json_data:
                    secrets_content = json.load(json_data)
                    ibrokers_flex_token = secrets_content['ibrokers.flex.token']

            accounts = flex_request(ibrokers_flex_token)

        for account_id in accounts:
            account_data = accounts[account_id]
            attachment_description = '{} ({}) - {}'.format(
                account_data['account_id'],
                account_data['account_alias'],
                account_data['currency']
            )
            attachment = {'color': '#F35A00', 'text': attachment_description}
            account_fields = [
                {'title': 'NAV change ({})'.format(account_data['as_of_date']),
                 'value': '{0:,g}'.format(account_data['nav_change']), 'short': False},
                {'title': 'NAV', 'value': '{0:,g}'.format(account_data['nav_end']), 'short': True},
                {'title': 'NAV (prev)', 'value': '{0:,g}'.format(account_data['nav_start']), 'short': True}
            ]
            attachment['fields'] = account_fields
            attachments.append(attachment)

        message_body = '*Daily reporting - NAV changes*'

    slack_client = SlackClient(slack_api_token)
    slack_client.api_call('chat.postMessage',
                          channel='#' + _SLACK_CHANNEL,
                          text=message_body,
                          mrkdwn=True,
                          attachments=attachments)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(name)s:%(levelname)s:%(message)s')
    logging.getLogger('requests').setLevel(logging.WARNING)
    file_handler = logging.FileHandler('hdb.log', mode='w')
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)
    parser = argparse.ArgumentParser(description='Daily risk data retrieval.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    parser.add_argument('--slack-api-token', type=str, help='slack API token')
    parser.add_argument('--ibrokers-flex-token', type=str, help='InteractiveBrokers Flex token')
    parser.add_argument('--use-message', type=str, help='sends message to slack channel')
    parser.add_argument('--use-file', type=str, help='sends message using indicated file')

    args = parser.parse_args()
    main(args)
