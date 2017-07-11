from collections import namedtuple
import re
import itertools
from datetime import datetime

import lxml.etree
import requests

WIDTH = 40
DATA_URL = 'http://www.hamqsl.com/solarxml.php'

HFBandConditions = namedtuple(
    'HFBandConditions', ('band', 'time', 'condition'))


def fetch_xml_data():
    resp = requests.get(DATA_URL)
    assert resp.ok
    return lxml.etree.fromstring(resp.content)


def extract_data(tree):

    DATE_FORMAT = '%d %b %Y %H%M GMT'

    solardata = tree.xpath('/solar/solardata')[0]

    return {
        'updated': datetime.strptime(
            solardata.xpath('updated/text()')[0].strip(),
            DATE_FORMAT),

        'solarflux': int(solardata.xpath('solarflux/text()')[0]),
        'aindex': int(solardata.xpath('aindex/text()')[0]),
        'kindex': int(solardata.xpath('kindex/text()')[0]),
        'kindexnt': solardata.xpath('kindexnt/text()')[0],
        'xray': solardata.xpath('xray/text()')[0],
        'sunspots': int(solardata.xpath('sunspots/text()')[0]),
        'heliumline': float(solardata.xpath('heliumline/text()')[0]),
        'protonflux': float(solardata.xpath('protonflux/text()')[0]),
        'electronflux': float(solardata.xpath('electonflux/text()')[0]),
        'aurora': int(solardata.xpath('aurora/text()')[0]),
        'normalization': float(solardata.xpath('normalization/text()')[0]),
        'latdegree': float(solardata.xpath('latdegree/text()')[0]),
        'solarwind': float(solardata.xpath('solarwind/text()')[0]),
        'magneticfield': float(solardata.xpath('magneticfield/text()')[0]),
        'geomagfield': solardata.xpath('geomagfield/text()')[0],
        'signalnoise': solardata.xpath('signalnoise/text()')[0],
        'fof2': solardata.xpath('fof2/text()')[0],
        'muffactor': solardata.xpath('muffactor/text()')[0],
        'muf': solardata.xpath('muf/text()')[0],

        'hf_conditions': extract_hf_conditions(solardata),
    }


def extract_hf_conditions(data):
    return list(_extract_hf_conditions(data))


def _extract_hf_conditions(data):

    items = list(_find_hf_conditions(data))
    items.sort(key=lambda x: (x.band, x.time), reverse=True)

    for band_name, conditions in itertools.groupby(items, lambda x: x.band):
        cond = {}
        for c in conditions:
            cond[c.time] = c.condition
        yield {
            'band': band_name,
            'conditions': cond,
        }


def _find_hf_conditions(data):

    re_band_range = re.compile('^([0-9]+)m-([0-9]+)m$')

    for item in data.xpath('calculatedconditions/band'):
        _band = item.attrib['name']
        m = re_band_range.match(_band)
        band = (int(m.group(1)), int(m.group(2)))

        yield HFBandConditions(
            band=band,
            time=item.attrib['time'],
            condition=item.text)


if __name__ == '__main__':
    tree = fetch_xml_data()

    # def jsondefault(obj):
    #     if isinstance(obj, datetime):
    #         return obj.isoformat()
    #     raise TypeError

    data = extract_data(tree)

    print('Solar-Terrestrial Data '.ljust(WIDTH, '-'))
    print('Update: \x1b[1;33m{}\x1b[0m'.format(data['updated'].isoformat()))
    print('Solar flux: \x1b[32m{}\x1b[0m'.format(data['solarflux']))
    print('Sun spots: \x1b[32m{}\x1b[0m'.format(data['sunspots']))
    print('A-Index: \x1b[32m{}\x1b[0m'.format(data['aindex']))
    print('K-Index: \x1b[32m{}\x1b[0m'.format(data['kindex']))
    print('X-Ray: \x1b[32m{}\x1b[0m'.format(data['xray']))
    print('304A: \x1b[32m{}\x1b[0m'.format(data['heliumline']))

    print(' HF Conditions '.center(WIDTH, '-'))

    def _format_condition(c):
        if c == 'Poor':
            return '\x1b[1;31mPoor\x1b[0m'
        if c == 'Fair':
            return '\x1b[1;33mFair\x1b[0m'
        if c == 'Good':
            return '\x1b[1;32mGood\x1b[0m'
        return c

    print('\x1b[1mBand      Day     Night\x1b[0m')
    for item in data['hf_conditions']:
        print('{:28}{:19}{:20}'
              .format('\x1b[36m{0}\x1b[0mm-\x1b[36m{1}\x1b[0mm'
                      .format(*item['band']),
                      _format_condition(item['conditions']['day']),
                      _format_condition(item['conditions']['night'])))
        pass
