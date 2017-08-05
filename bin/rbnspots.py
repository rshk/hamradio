from datetime import datetime
from decimal import Decimal
from typing import Dict, List, NamedTuple

import click
import requests
from pytz import utc
import time


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
    # .replace(tzinfo=utc)
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
    for callsign, callinfo in response['ci'].items():
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
    for spotid, spotinfo in response['s'].items():
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


def get_spots(cdx, s=0, r=15):
    url = 'http://www.reversebeacon.net/dxsd1/sk.php'
    query = {'cdx': str(cdx), 's': str(s), 'r': str(r)}
    response = requests.get(url, params=query)

    if not response.ok:
        print('Error response: {}'.format(response.status_code))
        print(response.text)
        raise Exception('Request failed')

    resp = response.json()
    return parse_response(resp)


@click.command()
@click.argument('callsign')
def main(callsign):
    resp = get_spots(callsign)
    for spot in resp.spots:
        click.echo(
            '\x1b[34m{s.timestamp:%Y-%m-%d %H:%M:%S}\x1b[0m '
            '\x1b[1m{s.spot_de:^10s}\x1b[0m '
            '{mhz:>10.6g} MHz  '
            '\x1b[1m{s.snr:>2d} dB\x1b[0m  {s.speed:>2d} wpm  '
            '\x1b[33m{de.country_name}\x1b[0m '
            '\x1b[32m[ITU:{de.itu_zone} CQ:{de.cq_zone}]\x1b[0m '
            '\x1b[36m{de.latitude},{de.longitude}\x1b[0m'
            .format(s=spot,
                    mhz=spot.frequency / 1000,
                    de=resp.callsigns[spot.spot_de]))


if __name__ == '__main__':
    main()
