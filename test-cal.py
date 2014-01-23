#!/usr/bin/env python

# groupwise-ics: synchronize GroupWise calendar to ICS file and back
# Copyright (C) 2013  Cedric Bosdonnat <cedric@bosdonnat.fr>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import datetime
import cal

def tzdetails_from_dict(values):
    tzdetails = cal.TZDetails(values['kind'])
    tzdetails.name = values['name']
    tzdetails.parseline('DTSTART:%s' % values['start'])
    tzdetails.parseline('TZOFFSETFROM:%s' % values['offsetfrom'])
    tzdetails.parseline('TZOFFSETTO:%s' % values['offsetto'])
    return tzdetails

def create_parametrized_value(params, value):
    parametrized = cal.ParametrizedValue('')
    parametrized.params = params
    parametrized.value = value
    return parametrized

def create_email(ical):
    mail = '\r\n'.join(['Mime-Version: 1.0',
                        'X-Mailer: GroupWise 2012',
                        'Subject: Title',
                        'Date: Wed, 15 Jan 2014 14:46:00 +0000',
                        'Message-ID: <xxxxxx@hacker.com>',
                        'From: "Joe Hacker" <joe@hacker.com>',
                        'To: Bob Hacker <bob@hacker.com>',
                        'Content-Type: text/calendar',
                        '',
                        ical])
    return mail

def load_from_file(path):
    fdescr = open(path, 'r')
    content = fdescr.read()
    fdescr.close()
    return content

class CalendarTest(unittest.TestCase):

    def test_timezone_utcoffset(self):
        tz = cal.Timezone()
        tz.tzid = 'Some id'
        tz.changes = [ tzdetails_from_dict({'kind': 'DAYLIGHT', 'name': 'CEST',
                                            'start': '20130331T020000', 'offsetfrom': '+0100',
                                            'offsetto': '+0200'}),
                       tzdetails_from_dict({'kind': 'STANDARD', 'name': 'CET',
                                            'start': '20131027T030000', 'offsetfrom': '+0200',
                                            'offsetto': '+0100'}) ]
        dt = datetime.datetime(2013, 10, 8, 13, 0, 0)
        utc = dt - tz.utcoffset(dt)
        self.assertEqual(utc.strftime('%Y%m%dT%H%M%SZ'), '20131008T110000Z')

    def test_parse_vtimezone_simple(self):
        data = ['TZID:/freeassociation.sourceforge.net/Tzfile/Europe/Paris',
                'X-LIC-LOCATION:Europe/Paris',
                'BEGIN:DAYLIGHT',
                'TZNAME:CEST',
                'DTSTART:20130331T020000',
                'TZOFFSETFROM:+0100',
                'TZOFFSETTO:+0200',
                'END:DAYLIGHT',
                'BEGIN:STANDARD',
                'TZNAME:CET',
                'DTSTART:20131027T030000',
                'TZOFFSETFROM:+0200',
                'TZOFFSETTO:+0100',
                'END:STANDARD']

        tz = cal.Timezone()
        for line in data:
            tz.parseline(line)

        expected_changes = [ tzdetails_from_dict({'kind': 'DAYLIGHT', 'name': 'CEST',
                                            'start': '20130331T020000', 'offsetfrom': '+0100',
                                            'offsetto': '+0200'}),
                             tzdetails_from_dict({'kind': 'STANDARD', 'name': 'CET',
                                            'start': '20131027T030000', 'offsetfrom': '+0200',
                                            'offsetto': '+0100'}) ]
        self.assertEqual(tz.changes, expected_changes)
        self.assertEqual(tz.tzid, '/freeassociation.sourceforge.net/Tzfile/Europe/Paris'.lower())

    def test_timezone_rrule(self):
        data = ['TZID:Mountain Standard Time',
                'BEGIN:STANDARD',
                'TZOFFSETFROM:-0600',
                'TZOFFSETTO:-0700',
                'DTSTART:20001102T020000',
                'RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11',
                'TZNAME:Mountain Standard Time',
                'END:STANDARD',
                'BEGIN:DAYLIGHT',
                'TZOFFSETFROM:-0700',
                'TZOFFSETTO:-0600',
                'DTSTART:20000309T020000',
                'RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3',
                'TZNAME:Mountain Daylight Time',
                'END:DAYLIGHT']
        tested = cal.Timezone()
        for line in data:
            tested.parseline(line)

        # Test winter offset
        actual = tested.utcoffset(datetime.datetime(2014, 1, 21, 9, 0, 0))
        self.assertEqual(actual, datetime.timedelta(hours=-7))

        # Test summer offset
        actual = tested.utcoffset(datetime.datetime(2014, 6, 21, 9, 0, 0))
        self.assertEqual(actual, datetime.timedelta(hours=-6))

    def test_parametrized_values_equals(self):
        parametrized_values1 = [ create_parametrized_value( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'ACCEPTED', 'RSVP': 'TRUE', \
                                               'CN': 'Joe HACKER', 'LANGUAGE': 'en'}, 'MAILTO:joe@hacker.com' ),
                          create_parametrized_value( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'NEEDS-ACTION', 'RSVP': 'TRUE', \
                                               'LANGUAGE': 'en'}, 'MAILTO:alice@hacker.com' ) ]
        parametrized_values2 = [ create_parametrized_value( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'NEEDS-ACTION', 'RSVP': 'TRUE', \
                                               'LANGUAGE': 'en'}, 'MAILTO:alice@hacker.com' ),
                          create_parametrized_value( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'ACCEPTED', 'RSVP': 'TRUE', \
                                               'CN': 'Joe HACKER', 'LANGUAGE': 'en'}, 'MAILTO:joe@hacker.com' ) ]
        self.assertTrue( len(set(parametrized_values1) ^ set(parametrized_values2)) == 0 )

    def test_parse_event(self):
        data = '\r\n'.join(['BEGIN:VCALENDAR',
                            'PRODID:-//Ximian//NONSGML Evolution Calendar//EN',
                            'VERSION:2.0',
                            'METHOD:REQUEST',
                            'BEGIN:VEVENT',
                            'UID:20131007T194020Z-3587-100-1732-0@laptop',
                            'DTSTAMP:20131007T194119Z',
                            'DTSTART:20131008T130000Z',
                            'DTEND:20131008T133000Z',
                            'TRANSP:OPAQUE',
                            'SEQUENCE:2',
                            'SUMMARY:test summary',
                            'LOCATION:test location',
                            'DESCRIPTION:test description',
                            'CLASS:PUBLIC',
                            'ORGANIZER;CN=Joe Hacker:MAILTO:joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;',
                            ' RSVP=TRUE;CN=Joe HACKER;LANGUAGE=en:MAILTO:',
                            ' joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;',
                            ' RSVP=TRUE;LANGUAGE=en:MAILTO:alice@hacker.com',
                            'END:VEVENT',
                            'END:VCALENDAR'])
        parsed = cal.Calendar(create_email(data))

        expected_event = cal.Event(None)
        expected_event.uid = '20131007T194020Z-3587-100-1732-0@laptop'
        expected_event.dtstamp = '20131007T194119Z' # dtstamp should always be a datetime in UTC
        expected_event.dtstart = ':20131008T130000Z'
        expected_event.dtend = ':20131008T133000Z'
        expected_event.summary = 'test summary'
        expected_event.location = 'test location'
        expected_event.description = 'test description'
        expected_event.organizer = create_parametrized_value( {'CN': 'Joe Hacker' }, 'MAILTO:joe@hacker.com' )
        expected_event.attendees = [ create_parametrized_value( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                                          'PARTSTAT': 'ACCEPTED', 'RSVP': 'TRUE', \
                                                          'CN': 'Joe HACKER', 'LANGUAGE': 'en'}, 'MAILTO:joe@hacker.com' ),
                                     create_parametrized_value( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                                          'PARTSTAT': 'NEEDS-ACTION', 'RSVP': 'TRUE', \
                                                          'LANGUAGE': 'en'}, 'MAILTO:alice@hacker.com' ) ]
        self.assertEqual(parsed.events[0], expected_event)

    def test_parse_mail_attachement(self):
        mail = load_from_file('tests/attach.eml')
        tested = cal.Calendar(mail)
        tested_event = tested.events[0]

        expected = create_parametrized_value({'FMTTYPE': 'text/plain',
                                              'X-FILENAME': 'foo.txt',
                                              'ENCODING': 'BASE64',
                                              'VALUE': 'BINARY'},
                                             'c29tZSBjb250ZW50')
        self.assertEqual(tested_event.attachments[0], expected)

    def test_calendar_diff_added(self):
        data_old = '\r\n'.join(['BEGIN:VCALENDAR',
                            'PRODID:-//Ximian//NONSGML Evolution Calendar//EN',
                            'VERSION:2.0',
                            'METHOD:REQUEST',
                            'BEGIN:VEVENT',
                            'UID:old-event-uid',
                            'DTSTAMP:20131007T194119Z',
                            'DTSTART:20131008T130000Z',
                            'DTEND:20131008T133000Z',
                            'TRANSP:OPAQUE',
                            'SEQUENCE:2',
                            'SUMMARY:test summary',
                            'LOCATION:test location',
                            'DESCRIPTION:test description',
                            'CLASS:PUBLIC',
                            'ORGANIZER;CN=Joe Hacker:MAILTO:joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;',
                            ' RSVP=TRUE;CN=Joe HACKER;LANGUAGE=en:MAILTO:',
                            ' joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;',
                            ' RSVP=TRUE;LANGUAGE=en:MAILTO:alice@hacker.com',
                            'END:VEVENT',
                            'END:VCALENDAR'])
        old = cal.Calendar(create_email(data_old))

        data_new = '\r\n'.join(['BEGIN:VCALENDAR',
                            'PRODID:-//Ximian//NONSGML Evolution Calendar//EN',
                            'VERSION:2.0',
                            'METHOD:REQUEST',
                            'BEGIN:VEVENT',
                            'UID:old-event-uid',
                            'DTSTAMP:20131007T194119Z',
                            'DTSTART:20131008T130000Z',
                            'DTEND:20131008T133000Z',
                            'TRANSP:OPAQUE',
                            'SEQUENCE:2',
                            'SUMMARY:test summary',
                            'LOCATION:test location',
                            'DESCRIPTION:test description',
                            'CLASS:PUBLIC',
                            'ORGANIZER;CN=Joe Hacker:MAILTO:joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;',
                            ' RSVP=TRUE;CN=Joe HACKER;LANGUAGE=en:MAILTO:',
                            ' joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;',
                            ' RSVP=TRUE;LANGUAGE=en:MAILTO:alice@hacker.com',
                            'END:VEVENT',
                            'BEGIN:VEVENT',
                            'UID:added-event-uid',
                            'DTSTAMP:20131009T194119Z',
                            'DTSTART:20131010T130000Z',
                            'DTEND:20131010T133000Z',
                            'TRANSP:OPAQUE',
                            'SEQUENCE:2',
                            'SUMMARY:added event summary',
                            'LOCATION:added event location',
                            'DESCRIPTION:added event description',
                            'CLASS:PUBLIC',
                            'ORGANIZER;CN=Joe Hacker:MAILTO:joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;',
                            ' RSVP=TRUE;LANGUAGE=en:MAILTO:bob@hacker.com',
                            'END:VEVENT',
                            'END:VCALENDAR'])
        new = cal.Calendar(create_email(data_new))

        (changed, removed, added, unchanged) = old.diff(new)

        self.assertEqual(len(changed), 0)
        self.assertEqual(len(removed), 0)
        self.assertEqual(added.keys()[0], 'added-event-uid')
        self.assertEqual(unchanged.keys()[0], 'old-event-uid')

    def test_calendar_diff_changed(self):
        data_old = '\r\n'.join(['BEGIN:VCALENDAR',
                            'PRODID:-//Ximian//NONSGML Evolution Calendar//EN',
                            'VERSION:2.0',
                            'METHOD:REQUEST',
                            'BEGIN:VEVENT',
                            'UID:changed-event-uid',
                            'DTSTAMP:20131007T194119Z',
                            'DTSTART:20131008T130000Z',
                            'DTEND:20131008T133000Z',
                            'TRANSP:OPAQUE',
                            'SEQUENCE:2',
                            'SUMMARY:test summary',
                            'LOCATION:test location',
                            'DESCRIPTION:test description',
                            'CLASS:PUBLIC',
                            'ORGANIZER;CN=Joe Hacker:MAILTO:joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;',
                            ' RSVP=TRUE;CN=Joe HACKER;LANGUAGE=en:MAILTO:',
                            ' joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;',
                            ' RSVP=TRUE;LANGUAGE=en:MAILTO:alice@hacker.com',
                            'END:VEVENT',
                            'END:VCALENDAR'])
        old = cal.Calendar(create_email(data_old))

        data_new = '\r\n'.join(['BEGIN:VCALENDAR',
                            'PRODID:-//Ximian//NONSGML Evolution Calendar//EN',
                            'VERSION:2.0',
                            'METHOD:REQUEST',
                            'BEGIN:VEVENT',
                            'UID:changed-event-uid',
                            'DTSTAMP:20131007T194119Z',
                            'DTSTART:20131008T130000Z',
                            'DTEND:20131008T133000Z',
                            'TRANSP:OPAQUE',
                            'SEQUENCE:2',
                            'SUMMARY:test summary',
                            'LOCATION:test location',
                            'DESCRIPTION:test description',
                            'CLASS:PUBLIC',
                            'ORGANIZER;CN=Joe Hacker:MAILTO:joe@hacker.com',
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;',
                            ' RSVP=TRUE;CN=Bob HACKER;LANGUAGE=en:MAILTO:',    # Participant changed from
                            ' bob@hacker.com',                                 # Joe to Bob
                            'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;',
                            ' RSVP=TRUE;LANGUAGE=en:MAILTO:alice@hacker.com',
                            'END:VEVENT',
                            'END:VCALENDAR'])
        new = cal.Calendar(create_email(data_new))

        (changed, removed, added, unchanged) = old.diff(new)

        self.assertEqual(len(unchanged), 0)
        self.assertEqual(len(removed), 0)
        self.assertEqual(len(added), 0)
        self.assertEqual(changed.keys()[0], 'changed-event-uid')

if __name__ == '__main__':
    unittest.main()
