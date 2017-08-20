"""RBN spots

Show "spots" from the Reverse Beacon Network (http://reversebeacon.net/).

Copyright (c) 2017 Samuele Santi

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

import logging
import sys
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, NamedTuple

import click
import requests
from pytz import utc

logger = logging.getLogger(__name__)


class RequestFailed(Exception):
    def __init__(self, *args, response=None, **kwargs):
        self.response = response
        super().__init__(*args, **kwargs)


class CallInfo(NamedTuple):
    callsign: str
    country_prefix: str
    country_name: str
    continent: str
    country_tld: str
    itu_zone: int
    cq_zone: int
    latitude: float
    longitude: float


class SpotInfo(NamedTuple):
    id: str
    spot_de: str  # Received
    frequency: Decimal
    spot_dx: str  # Transmitted
    snr: int  # Signal noise ratio, dB
    speed: int  # WPM
    timestamp: datetime


class Response(NamedTuple):
    callsigns: Dict[str, CallInfo]
    spots: List[SpotInfo]


def parse_date(date):
    current = time.gmtime()
    parsed = time.strptime(date, '%H%Mz %d %b')

    cur_md = current.tm_mon, current.tm_mday
    par_md = parsed.tm_mon, parsed.tm_mday

    if par_md > cur_md:
        # Must be last year
        year = current.tm_year - 1
    else:
        year = current.tm_year

    return datetime(
        year, parsed.tm_mon, parsed.tm_mday,
        parsed.tm_hour, parsed.tm_min, parsed.tm_sec,
        tzinfo=utc)


def parse_response(response):
    callsigns = {}

    for callsign, callinfo in response.get('ci', {}).items():
        callsigns[callsign] = CallInfo(
            callsign=callsign,
            country_prefix=callinfo[0],
            country_name=callinfo[1],
            continent=callinfo[2],
            country_tld=callinfo[3],
            itu_zone=int(callinfo[4]),
            cq_zone=int(callinfo[5]),
            latitude=float(callinfo[6]),
            longitude=float(callinfo[7]))

    spots = []
    for spotid, spotinfo in response.get('s', {}).items():
        spots.append(SpotInfo(
            id=spotid,
            spot_de=spotinfo[0],
            frequency=Decimal(spotinfo[1]),
            spot_dx=spotinfo[2],
            snr=spotinfo[3],
            speed=spotinfo[4],
            timestamp=parse_date(spotinfo[5]),
        ))

    return Response(callsigns, spots)


def _get_spots(callsign, s=0, rows=30):
    url = 'http://www.reversebeacon.net/dxsd1/sk.php'
    query = {'cdx': str(callsign),
             's': str(s),
             'r': str(rows)}
    response = requests.get(url, params=query)

    if not response.ok:
        raise RequestFailed(
            'Request failed with code {}: {}'
            .format(response.status_code, response.text),
            response=response)

    resp = response.json()
    return parse_response(resp)


def get_spots(*args, retries=5, retry_time=2, **kwargs):
    try:
        return _get_spots(*args, **kwargs)
    except RequestFailed as e:
        logger.error('Request failed with code %s. Retry in %s seconds.',
                     str(e.response.status_code), retry_time)
        if retries > 0:
            time.sleep(retry_time)
            return get_spots(*args, retries=(retries - 1), **kwargs)
        raise


def watch(callsign, watch_time=60):
    old_spots = set()

    while True:
        try:
            resp = get_spots(callsign)
        except RequestFailed:
            logger.error('All requests failed')

        new_spots = list(
            spot for spot in resp.spots
            if spot.id not in old_spots)

        if len(new_spots) > 0:
            logger.info('Received {} new spots'.format(len(new_spots)))

            for spot in new_spots:
                click.echo(format_spot(spot, resp.callsigns))
                old_spots.add(spot.id)

        else:
            logger.info('No new spots')

        time.sleep(watch_time)


def format_spot(spot, callsigns):
    return (
        '\x1b[34m{s.timestamp:%Y-%m-%d %H:%M:%S}\x1b[0m '
        '\x1b[1m{s.spot_de:^10s}\x1b[0m '
        '{mhz:>10.6g} MHz  '
        '\x1b[1m{s.snr:>2d} dB\x1b[0m  {s.speed:>2d} wpm  '
        '\x1b[33m{de.country_name}\x1b[0m '
        '\x1b[32m[ITU:{de.itu_zone} CQ:{de.cq_zone}]\x1b[0m '
        '\x1b[36m{de.latitude},{de.longitude}\x1b[0m'
        .format(s=spot,
                mhz=spot.frequency / 1000,
                de=callsigns[spot.spot_de]))


@click.command()
@click.argument('callsign')
@click.option('--watch', 'should_watch', is_flag=True, default=False)
@click.option('--watch-time', type=int, default=60)
def main(callsign, should_watch, watch_time):
    if (should_watch):
        return watch(callsign, watch_time)

    resp = get_spots(callsign)
    for spot in resp.spots:
        click.echo(format_spot(spot, resp.callsigns))


if __name__ == '__main__':
    handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    main()
