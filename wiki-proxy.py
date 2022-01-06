#!/usr/bin/env python3

from datetime import datetime
from flask import Flask, Response
from mwclient import Site as WikiSite
from wikitextparser import parse as wikiparse

import json


class Wiki:
    def __init__(self, device: str, buildid: str, *, boardconfig: str=None) -> None:
        self.site = WikiSite('www.theiphonewiki.com')

        self.device = device
        self.buildid = buildid
        self.board = boardconfig

    def get_firm_page(self) -> str:
        results = list(self.site.search(f'{self.buildid} ({self.device})'))
        if len(results) == 0:
            raise ValueError(f'No Firmware Keys page for device: {self.device}, buildid: {self.buildid}.')

        return self.site.pages[results[0]['title']].text()

    def parse_page(self, page: str) -> dict:
        page = ' '.join([x for x in page.split(' ') if x != '']).replace('{{', '{| class="wikitable"').replace('}}', '|}') # Have to coerce wikitextparser into recognizing it as a table for easy parsing
        page_data = dict()
        for entry in wikiparse(page).tables[0].data()[0]:
            key, item = entry.split(' = ')
            page_data[key] = item

        if self.board is not None:
            if ('Model' not in page_data.keys()) and ('Model2' not in page_data.keys()):
                return page_data

            if self.board.lower() not in [x.lower() for x in page_data.values()]:
                raise ValueError(f'Boardconfig: {self.board} for device: {self.device} is not valid!')

            if page_data['Model2'].lower() == self.board.lower():
                for key in page_data.keys():
                    if '2' in key:
                        page_data[key.replace('2', '')] = page_data[key]

            for key in list(page_data.keys()):
                if '2' in key:
                    del page_data[key]

        return page_data

    def get_keys(self, page: str) -> str:
        page_data = self.parse_page(page)
        response = {
            'identifier': page_data['Device'],
            'buildid': page_data['Build'],
            'codename': page_data['Codename'],
            'restoreramdiskexists': 'RestoreRamdisk' in page_data.keys(),
            'updateramdiskexists': 'UpdateRamdisk' in page_data.keys(),
            'keys': list()
        }

        for component in page_data.keys():
            if any(x == component for x in ('Version', 'Build', 'Device', 'Model', 'Codename', 'Baseband', 'DownloadURL')):
                continue

            if any(component.endswith(x) for x in ('Key', 'IV', 'KBAG')):
                continue

            image = {
                'image': component,
                'filename': page_data[component],
                'date': datetime.now().isoformat()
            }

            if any(component == x for x in ('RootFS', 'RestoreRamdisk', 'UpdateRamdisk')):
                image['filename'] += '.dmg'

            for key in ('IV', 'Key') if component != 'RootFS' else ('Key',):
                if component + key not in page_data.keys():
                    continue

                if any(x in page_data[component + key] for x in ('Unknown', 'Not Encrypted')):
                    continue

                image[key.lower()] = page_data[component + key]

            if ('iv' not in image.keys()) and ('key' not in image.keys()):
                if not image['filename'].endswith('.dmg'):
                    continue

            if ('iv' in image.keys()) and ('key' in image.keys()):
                image['kbag'] = image['iv'] + image['key']
                
            response['keys'].append(image)

        return json.dumps(response)


app = Flask('Wikiproxy API')

@app.route('/firmware/<device>/<buildid>', methods=['GET'])
def keys(device: str, buildid: str) -> Response:
    print(f'Getting firmware keys for device: {device}, buildid: {buildid}')
    iphonewiki = Wiki(device, buildid)
    try:
        page = iphonewiki.get_firm_page()
        keys = iphonewiki.get_keys(page)
        return app.response_class(response=keys, mimetype='application/json')
    except:
        return app.response_class(status=404)

@app.route('/firmware/<device>/<boardconfig>/<buildid>', methods=['GET'])
def keys_a9(device: str, boardconfig: str, buildid: str) -> Response:
    print(f'Getting firmware keys for device: {device} (boardconfig: {boardconfig}), buildid: {buildid}')
    iphonewiki = Wiki(device, buildid, boardconfig=boardconfig)
    try:
        page = iphonewiki.get_firm_page()
        keys = iphonewiki.get_keys(page)
        return app.response_class(response=keys, mimetype='application/json')
    except:
        return app.response_class(status=404)


if __name__ == '__main__':
    app.run(port=8888)
