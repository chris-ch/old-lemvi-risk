import json
import unittest
import os
import logging
from datetime import datetime

import pandas
from decimal import Decimal


def to_decimal(value):
    if type(value) == str:
        value = value.replace(',', '').replace("'", '')

    return Decimal(value)


def extract_flows(flows_data):
    converted_flows = list()
    for row in flows_data:
        flow_data = {'Date': datetime.strptime(row['Date'], '%Y-%m-%d').date()}
        for key in row:
            if key == 'Date':
                continue

            flow_data[key] = to_decimal(row[key])

        converted_flows.append(flow_data)

    return pandas.DataFrame(converted_flows)


def extract_navs(navs_data):
    concat_navs = pandas.DataFrame()
    for account, nav_data in navs_data.items():
        converted_flows = list()
        for item in nav_data:
            converted_flow = {
                'Date': datetime.strptime(item['Date'], '%Y-%m-%d').date(),
                'NAV UK': to_decimal(item['NAV UK']),
                'NAV US': to_decimal(item['NAV US']),
                'Total NAV': to_decimal(item['Total NAV']),
            }
            converted_flows.append(converted_flow)

        account_navs = pandas.DataFrame(converted_flows)
        account_navs['account'] = account
        concat_navs = pandas.concat([concat_navs, account_navs])

    return concat_navs


class TrackDrawdownTestCase(unittest.TestCase):

    def setUp(self):
        example_navs_file_path = os.path.abspath(os.sep.join(['tests-data', 'google-navs-data.json']))
        logging.info('loading example navs file: {}'.format(example_navs_file_path))
        with open(example_navs_file_path, 'r') as navs_file:
            navs_data = json.load(navs_file)
            self.flows = extract_navs(navs_data)[['Date', 'Total NAV', 'account']]
            print(self.flows.columns)

        example_flows_file_path = os.path.abspath(os.sep.join(['tests-data', 'google-flows-data.json']))
        logging.info('loading example flows file: {}'.format(example_flows_file_path))
        with open(example_flows_file_path, 'r') as flows_file:
            flows_data = json.load(flows_file)
            self.navs = extract_flows(flows_data)

    def test_drawdown(self):
        concatenated = pandas.concat([self.navs, self.flows])
        result = concatenated.sort_values('Date', ascending=False)
        print(result.head())

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(name)s:%(levelname)s:%(message)s')
    unittest.main()
