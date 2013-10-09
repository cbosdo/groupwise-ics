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

def create_participant(params, uri):
    participant = cal.Participant('')
    participant.params = params
    participant.uri = uri
    return participant

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

    def test_participants_equals(self):
        participants1 = [ create_participant( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'ACCEPTED', 'RSVP': 'TRUE', \
                                               'CN': 'Joe HACKER', 'LANGUAGE': 'en'}, 'MAILTO:joe@hacker.com' ),
                          create_participant( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'NEEDS-ACTION', 'RSVP': 'TRUE', \
                                               'LANGUAGE': 'en'}, 'MAILTO:alice@hacker.com' ) ]
        participants2 = [ create_participant( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'NEEDS-ACTION', 'RSVP': 'TRUE', \
                                               'LANGUAGE': 'en'}, 'MAILTO:alice@hacker.com' ), 
                          create_participant( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                               'PARTSTAT': 'ACCEPTED', 'RSVP': 'TRUE', \
                                               'CN': 'Joe HACKER', 'LANGUAGE': 'en'}, 'MAILTO:joe@hacker.com' ) ]
        self.assertTrue( len(set(participants1) ^ set(participants2)) == 0 )

    def test_parse_event(self):
        data = '\r\n'.join(['BEGIN:VCALENDAR',
                            'CALSCALE:GREGORIAN',
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
        parsed = cal.Calendar(data)

        expected_event = cal.Event(None)
        expected_event.uid = '20131007T194020Z-3587-100-1732-0@laptop'
        expected_event.dtstamp = '20131007T194119Z'
        expected_event.dtstart = '20131008T130000Z'
        expected_event.dtend = '20131008T133000Z'
        expected_event.summary = 'test summary'
        expected_event.location = 'test location'
        expected_event.description = 'test description'
        expected_event.organizer = create_participant( {'CN': 'Joe Hacker' }, 'MAILTO:joe@hacker.com' )
        expected_event.attendees = [ create_participant( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                                          'PARTSTAT': 'ACCEPTED', 'RSVP': 'TRUE', \
                                                          'CN': 'Joe HACKER', 'LANGUAGE': 'en'}, 'MAILTO:joe@hacker.com' ),
                                     create_participant( {'CUTYPE': 'INDIVIDUAL', 'ROLE': 'REQ-PARTICIPANT', \
                                                          'PARTSTAT': 'NEEDS-ACTION', 'RSVP': 'TRUE', \
                                                          'LANGUAGE': 'en'}, 'MAILTO:alice@hacker.com' ) ]
        self.assertEqual(parsed.events[0], expected_event)

if __name__ == '__main__':
    unittest.main()
