#!/usr/bin/env python2

from argparse import ArgumentParser
from os.path import expanduser, exists, basename

import webbrowser

import httplib2

import logging
from apiclient import discovery
from oauth2client import client
import cPickle

from datetime import date, datetime
from dateutil.tz import gettz, tzfile
from remind import Remind


if __name__ == '__main__':
    # Argument handling
    parser = ArgumentParser()
    parser.add_argument('-c', '--clear', nargs='?', const=True, default=False)
    parser.add_argument('-f', '--free', nargs='?', const=True, default=False)
    parser.add_argument('infile', nargs='?', default=expanduser('~/.reminders'))
    parser.add_argument('calID', nargs='?', default='primary')
    args = parser.parse_args()

    # OAuth 2.0
    logging.basicConfig()
    credentials_path = expanduser('~/.calauth')
    if exists(credentials_path):
        with open(credentials_path, 'r') as f:
            credentials = cPickle.load(f)
    else:
        flow = client.flow_from_clientsecrets(
          'client_secrets.json',
          scope='https://www.googleapis.com/auth/calendar',
          redirect_uri='urn:ietf:wg:oauth:2.0:oob',)

        auth_uri = flow.step1_get_authorize_url()
        webbrowser.open(auth_uri)
        auth_code = raw_input('Enter the auth code: ')
        credentials = flow.step2_exchange(auth_code)
        with open(credentials_path, 'w') as f:
            cPickle.dump(credentials, f)
    http_auth = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http_auth)
    events = service.events()

    # Load Remind data
    tz = 'Europe/Dublin'
    zone = gettz(tz)
    zone.zone = tz

    # Get calendar from 1990-01-01 to 15 months from today
    rem = Remind(args.infile, zone, startdate=date(1990, 1, 1),
            month=(12 * (date.today().year-1990) + (date.today().month) + 15))
    vcal = rem.to_vobject()

    # Clear calendar
    page_token = None
    old_events = []
    while True:
        old = events.list(
                calendarId=args.calID, pageToken=page_token).execute()
        old_events = old_events + old['items']
        page_token = old.get('nextPageToken')
        if not page_token:
            break
    for x in old_events:
        if ('extendedProperties' in x
                and x['extendedProperties']['private']['source'] ==
                basename(args.infile)):
            events.delete(calendarId=args.calID, eventId=x['id']).execute()
        elif args.clear:
            events.delete(calendarId=args.calID, eventId=x['id']).execute()

    utcfile = tzfile('/usr/share/zoneinfo/UTC')
    for vevent in vcal.contents['vevent']:
        event = {}
        event['summary'] = vevent.contents['summary'][0].value
        dt = vevent.contents['dtstart'][0].value

        # Timed event
        if isinstance(dt, datetime):
            dtstart = dt.astimezone(utcfile)
            duration = vevent.contents['duration'][0].value
            dtend = dtstart + duration
            event['start'] = {'dateTime': dtstart.isoformat()}
            event['end'] = {'dateTime': dtend.isoformat()}
        # All-day event
        else:
            event['start'] = {'date': dt.isoformat()}
            end = vevent.contents['dtend'][0].value
            event['end'] = {'date': end.isoformat()}

        # Recurring event
        if 'rdate' in vevent.contents:
            rdate = vevent.contents['rdate'][0].value
            # Timezone field is required for recurring events
            event['start']['timeZone'] = 'UTC'
            event['end']['timeZone'] = 'UTC'
            event['recurrence'] = []
            event['recurrence'].append('RDATE;TZID=UTC:%s' % ','.join(
                [r.isoformat().replace('-','').replace(':','')[:-5] + 'Z'
                for r in rdate]))
        event['uid'] = vevent.contents['uid'][0].value

        # Free event
        if args.free:
            event['transparency'] = 'transparent'
            event['colorId'] = 1
        # Busy event
        else:
            # Add alarm to busy events
            event['reminders'] = {'overrides':
                    [{"method": "popup", "minutes": 10}],
                    'useDefault': False}

        # current implementation doesn't export reminder times
        #if 'valarm' in vevent.contents:
        #    event['reminders'] = {'overrides': [], 'useDefault': False}
        #    for valarm in vevent.contents['valarm']:
        #        trigger = valarm.contents['trigger'][0].value
        #        delta = trigger * -1
        #        event['reminders']['overrides'].append({
        #            'method': 'popup',
        #            'minutes': delta.total_seconds() / 60})

        event['extendedProperties'] = {
                'private': {
                    'source': basename(args.infile)}
                }
        events.insert(calendarId=args.calID, body=event).execute()
