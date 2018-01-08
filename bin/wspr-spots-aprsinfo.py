#!/usr/bin/env python

"""Query WSPR (Whisper) spots via aprsinfo.com API

Copyright (c) 2018 Samuele Santi

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

1. Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import math
from datetime import datetime
from decimal import Decimal
from typing import NamedTuple
from urllib.parse import quote

import click
import requests
from pytz import utc

API_URL = ('http://wspr.aprsinfo.com/newload'
           '/{call}/{count}/{timelimit}/{direction}/{band}')


DIRECTION_OPTIONS = {
    'tx': 'call',
    'rx': 'reporter',
    'all': '-',
}


BAND_OPTIONS = {
    'All': 'All',
    'LF': '-1',
    'MF': '0',
    '160m': '1',
    '80m': '3',
    '60m': '5',
    '40m': '7',
    '30m': '10',
    '20m': '14',
    '17m': '18',
    '15m': '21',
    '12m': '24',
    '10m': '28',
    '6m': '50',
    '4m': '70',
    '2m': '144',
    '70cm': '432',
    '23cm': '1296',
}


def fetch_spots(call=None, count=50, timelimit=3600,
                direction=None, band=None):

    def q(x):
        return quote(str(x), '')

    url = API_URL.format(
        call=q(call or '-'),
        count=q(count),
        timelimit=q(timelimit),
        direction=q(direction or '-'),
        band=q(band or 'All'))

    print('>>> URL {}'.format(url))

    response = requests.get(url)

    if not response.ok:
        raise RequestFailed(
            'Request failed with code {}: {}'
            .format(response.status_code, response.text),
            response=response)

    resp = response.json()
    return list(decode_response(resp))


def decode_response(resp):
    for item in resp:
        yield ResponseItem(

            timestamp=datetime
            .strptime(item['0'], '%Y-%m-%d %H:%M')
            .replace(tzinfo=utc),

            tx_call=item['1'],
            freq=int(Decimal(item['2']) * 1000000),
            snr=int(item['3']),
            drift=int(item['4']),
            tx_grid=item['5'],
            tx_power=float(item['6']),
            rx_call=item['7'],
            rx_grid=item['8'],
            distance=int(item['9']),
            azimuth=int(item['10']),

            rx_loc=Point(
                lat=float(item['_source_lat']),
                lon=float(item['_source_lon'])),

            tx_loc=Point(
                lat=float(item['_target_lat']),
                lon=float(item['_target_lon'])))


class Point(NamedTuple):
    lat: float
    lon: float


class ResponseItem(NamedTuple):
    timestamp: datetime
    tx_call: str
    freq: int  # Hz
    snr: int  # dB
    drift: int
    tx_grid: str
    tx_power: int  # watts
    rx_call: str
    rx_grid: str
    distance: int  # km
    azimuth: int  # degrees
    rx_loc: Point
    tx_loc: Point


class RequestFailed(Exception):
    def __init__(self, *args, response=None, **kwargs):
        self.response = response
        super().__init__(*args, **kwargs)


def format_item(item):
    return (
        '\x1b[34m{item.timestamp:%Y-%m-%d %H:%M:%S}\x1b[0m '

        '{freq}  '

        '\x1b[1;41m TX \x1b[0m '
        '\x1b[1m{item.tx_call:<10s}\x1b[0m '
        '{item.tx_grid:<6} '

        '{item.snr:>3} dB '

        'D{item.drift:<+3} '

        '{power_w} '
        '{power_dbw} '

        '\x1b[1;42m RX \x1b[0m '
        '\x1b[1m{item.rx_call:<10s}\x1b[0m '
        '{item.rx_grid:<6} '

        '{item.distance:>5} km '
        '{azimuth}'

        .format(
            item=item,
            freq=format_frequency(item.freq),
            power_w=format_power_w(item.tx_power),
            power_dbw=format_power_dbw(item.tx_power),
            azimuth=format_direction(item.azimuth),
        )
    )
    pass


def format_frequency(freq):

    C_MHZ = '\x1b[1;38;5;49m'
    C_KHZ = '\x1b[1;38;5;37m'
    C_HZ = '\x1b[0;38;5;31m'
    C_RESET = '\x1b[0m'

    f_mhz = int(freq / 1000000)
    f_khz = int(freq / 1000 % 1000)
    f_hz = int(freq % 1000)
    return ('{}{:>4}.{}{:03d}.{}{:03d}{}'
            .format(C_MHZ, f_mhz, C_KHZ, f_khz, C_HZ, f_hz, C_RESET))


def format_power_dbw(power_w):
    power_dbw = round(math.log10(power_w) * 10)
    return '{:>3} dBW'.format(power_dbw)


def format_power_w(power_w):
    if power_w >= 1:
        return '{:>3} W '.format(round(power_w))

    if power_w >= .001:
        return '{:>3} mW'.format(round(power_w * 1000))

    return '{:>3} µW'.format(round(power_w * 1000000))


def format_direction(az):
    az = int(az)
    return '{:>3}\u00b0 {}'.format(az, _get_dir_icon(az))


def _get_dir_icon(az):
    idx = int(round(az / 45)) % 8
    return DIRECTION_ICONS[idx]


ICO_N = '\u2b06\ufe0f'
ICO_NE = '\u2197\ufe0f'
ICO_E = '\u27a1\ufe0f'
ICO_SE = '\u2198\ufe0f'
ICO_S = '\u2b07\ufe0f'
ICO_SW = '\u2199\ufe0f'
ICO_W = '\u2b05\ufe0f'
ICO_NW = '\u2196\ufe0f'

DIRECTION_ICONS = [ICO_N, ICO_NE, ICO_E, ICO_SE, ICO_S, ICO_SW, ICO_W, ICO_NW]


@click.command()
@click.option('-c', '--call', default=None)
@click.option('-n', '--count', type=int, default=50)
@click.option('-t', '--timelimit', type=int, default=3600)
@click.option('-d', '--direction', default=None)
@click.option('-b', '--band', default=None)
def main(call, count, timelimit, direction, band):

    if direction in DIRECTION_OPTIONS:
        direction = DIRECTION_OPTIONS[direction]

    spots = fetch_spots(
        call=call, count=count, timelimit=timelimit,
        direction=direction, band=band)

    for spot in spots:
        print(format_item(spot))


if __name__ == '__main__':
    main()
