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
import datetime
import time
from dateutil import rrule
import email
import os.path
import sys

class LineUnwrapper(object):
    def __init__(self, s):
        try:
            self.lines = s.split('\n')
        except:
            print >> sys.stderr, "Can't parse %s\n" % (s)
            self.lines = []
        self.lines_read = None
        self.saved = None

    def each_line(self):
        for line in self.lines:
            line = line.rstrip('\r')
            if line.startswith(' ') or line.startswith('\t'):
                if self.saved is None:
                    self.saved = ''
                    self.lines_read = []
                self.lines_read.append(line)
                self.saved += line.strip()
            else:
                if self.saved is not None:
                    retval = (self.lines_read, self.saved)
                    self.lines_read = [line]
                    self.saved = line.strip()
                    yield retval
                self.lines_read = [line]
                self.saved = line.strip()

class Calendar(object):
    def __init__(self, mailstr, attach_write_func=None):

        self.events = []
        mail = email.message_from_string(mailstr)
        ical = None
        attachments = []

        for part in mail.walk():
            if part.get_content_type().startswith('text/calendar'):
                ical = part.get_payload(decode=True)
            else:
                disposition = part.get('Content-Disposition')
                if disposition and disposition.startswith('attachment'):
                    attachment = {}
                    filename = part.get_filename()
                    if filename:
                        attachment['filename'] = filename
                    attachment['content-type'] = part.get_content_type()
                    attachment['payload'] = part.get_payload(decode=True)
                    attachments.append(attachment)
        if ical is None:
            print >> sys.stderr, "Didn't find any ical data in following email %s\n" % (mailstr)
        else:
            self.parse(ical, attachments, attach_write_func)

    def parse(self, ical, attachments, attach_write_func=None):
        content = LineUnwrapper(ical)
        vtimezone = None
        vevent = None
        tzmap = {}

        for (real_lines, line) in content.each_line():
            if vtimezone is not None:
                if line == 'END:VTIMEZONE':
                    tzmap[vtimezone.tzid] = vtimezone
                    vtimezone = None
                else:
                    vtimezone.parseline(line)
            elif vevent is None and line == 'BEGIN:VTIMEZONE':
                vtimezone = Timezone()
            elif vevent is not None:
                if line == 'END:VEVENT':
                    self.events.append(vevent)
                    vevent = None
                else:
                    vevent.parseline(real_lines, line, attachments,
                                     attach_write_func)
            elif vtimezone is None and line == 'BEGIN:VEVENT':
                vevent = Event(tzmap)

    def diff(self, calendar):
        '''
        Searches for differences between this calendar (origin)
        and the one passed as parameter.

        @result: (changed, removed, added, unchanged) where all items
                 in the tupple is a dictionary with a unique ID as key
                 and the event as value. Items in the changed dictionary
                 are dictionaries with 'old' and 'new' keys to store both
                 the old and new version of the event
        '''

        # First search for changed or removed events
        changed = {}
        removed = {}
        unchanged = {}

        orig_events = self.get_events_by_uid()
        dest_events = calendar.get_events_by_uid()
        for uid in orig_events:
            if uid in dest_events:
                if orig_events[uid] == dest_events[uid]:
                    unchanged[uid] = orig_events[uid]
                else:
                    changed[uid] = {'old': orig_events[uid], 'new': dest_events[uid]}
            else:
                removed[uid] = orig_events[uid]

        # Then search for new events
        added = {}
        for uid in dest_events:
            if uid not in orig_events:
                added[uid] = dest_events[uid]

        return (changed, removed, added, unchanged)

    def get_events_by_uid(self):
        by_uid = {}
        for event in self.events:
            uid = event.uid
            if event.gwrecordid is not None:
                uid = event.gwrecordid
            by_uid[uid] = event
        return by_uid

    def to_ical(self):
        out = ''

        out  = 'BEGIN:VCALENDAR\r\n'
        out += 'PRODID:-//SUSE Hackweek//NONSGML groupwise-to-ics//EN\r\n'
        out += 'VERSION:2.0\r\n'

        for event in self.events:
            out += event.to_ical()

        out += 'END:VCALENDAR\r\n'
        return out


class Timezone(datetime.tzinfo):
    def __init__(self):
        self.tzid = None
        self.component = None
        self.changes = []

    def parseline(self, line):
        if line.startswith('TZID:'):
            self.tzid = line[len('TZID:'):].lower().translate(None, '"\'')
        elif self.component is None and line.startswith('BEGIN:'):
            value = line[len('BEGIN:'):]
            self.component = TZDetails(value)
        elif self.component is not None:
            if line.startswith('END:'):
                self.changes.append(self.component)
                sorted(self.changes, key = lambda change: change.start)
                self.component = None
            else:
                self.component.parseline(line)

    def utcoffset(self, dt):
        offset = None
        # Build a list of sorted changes
        all_changes = {}
        now = datetime.datetime.now()
        for change in self.changes:
            if change.start:
                all_changes[change.start] = change
            else:
                it = iter(change.rrule)
                try:
                    date = it.next()
                    # Who plans meetings in 10 years from now?
                    while date.year < now.year + 10:
                        date = it.next()
                        all_changes[date] = change
                except StopIteration:
                    pass

        # Find the matching change
        for date in sorted(all_changes.keys()):
            if dt >= date:
                offset = all_changes[date].offsetto
            else:
                if offset is None:
                    return all_changes[date].offsetfrom
                else:
                    return offset
        return offset


class TZDetails(object):
    def __init__(self, kind):
        self.kind = kind
        self.name = None
        self.offsetfrom = 0
        self.offsetto = 0
        self.start = None
        self.rrule = None

    def parseline(self, line):
        if line.startswith('TZNAME:'):
            self.name = line[len('TZNAME:'):]
        if line.startswith('DTSTART:'):
            value = line[len('DTSTART:'):]
            self.start = datetime.datetime.strptime(value, '%Y%m%dT%H%M%S')
            if self.rrule:
                self.rrule = rrule.rrulestr(self.rrule, dtstart=self.start)
                self.start = None
        if line.startswith('TZOFFSETFROM:'):
            value = line[len('TZOFFSETFROM:'):]
            self.offsetfrom = self.parseoffset(value)
        if line.startswith('TZOFFSETTO:'):
            value = line[len('TZOFFSETTO:'):]
            self.offsetto = self.parseoffset(value)
        if line.startswith('RRULE:'):
            self.rrule = line[len('RRULE:'):]
            if self.start:
                self.rrule = rrule.rrulestr(self.rrule, dtstart=self.start)
                self.start = None

    def parseoffset(self, value):
        try:
            minutes = int(value[-2:])
            hours = int(value[-4:-2])
            sign = 1
            if len(value) == 5 and value[0] == '-':
                sign = -1
            minutes = sign * ( minutes + hours * 60 )
            return datetime.timedelta(minutes = minutes)
        except ValueError:
            return None

    def __eq__(self, other):
        return self.kind == other.kind and \
               self.name == other.name and \
               self.offsetfrom == other.offsetfrom and \
               self.offsetto == other.offsetto and \
               self.start == other.start

class ParametrizedValue(object):
    def __init__(self, ical):
        pos = ical.find(':')

        self.value = None

        # Split the value from the parameters
        if pos >= 0:
            self.value = ical[pos + 1:]
            params = ical[:pos].split(';')
        else:
            params = ical.split(';')

        # Process the parameters
        new_params = {}
        for param in params:
            pos = param.find('=')
            if pos >= 0:
                key = param[:pos]
                new_params[key] = param[pos + 1:]
        self.params = new_params

    def set_params(self, value):
        self._params = {}
        # Upper case all keys to avoid potential problems
        for param in value:
            self._params[param.upper()] = value[param]
    def get_params(self):
        return self._params;
    params = property(get_params, set_params)

    def __eq__(self, other):
        params_equals = set(self.params.items()) ^ set(other.params.items())
        return self.value == other.value and len(params_equals) == 0

    def __repr__(self):
        return self.to_ical()

    def __hash__(self):
        return hash(repr(self))

    def to_ical(self):
        result = ''
        for param in self.params:
            result += ';%s=%s' % (param, self.params[param])
        result += ':%s' % self.value
        return result

class Event(object):
    def __init__(self, tzmap):
        self.lines = []
        self.properties = {}
        self.tzmap = tzmap
        self.attendees = []
        self.attachments = []

    def get_property(self, key):
        value = None
        if key in self.properties:
            value = self.properties[key][0]
        return value
    def set_property(self,value, key, pattern):
        if key in self.properties:
            lineno = self.properties[key][1]
            del self.lines[lineno]
            del self.properties[key]
        lineno = len(self.lines)
        self.lines.append(pattern % value)
        self.properties[key] = (value, lineno)

    def get_uid(self):
        return self.get_property('uid')
    def set_uid(self, uid):
        self.set_property(uid, 'uid', 'UID:%s')
    uid = property(get_uid, set_uid)

    def get_gwrecordid(self):
        return self.get_property('gwrecordid')
    def set_gwrecordid(self, value):
        self.set_property(value, 'gwrecordid', 'X-GWRECORDID:%s')
    gwrecordid = property(get_gwrecordid, set_gwrecordid)

    def get_dtstamp(self):
        return self.get_property('dtstamp')
    def set_dtstamp(self, value):
        self.set_property(value, 'dtstamp', 'DTSTAMP:%s')
    dtstamp = property(get_dtstamp, set_dtstamp)

    def get_dtstart(self):
        """
        starts with a ':' in most cases as this can have parameters (for all-day events)
        """
        return self.get_property('dtstart')
    def set_dtstart(self, value):
        self.set_property(value, 'dtstart', 'DTSTART%s')
    dtstart = property(get_dtstart, set_dtstart)

    def get_dtend(self):
        """
        starts with a ':' in most cases as this can have parameters (for all-day events)
        """
        return self.get_property('dtend')
    def set_dtend(self, value):
        self.set_property(value, 'dtend', 'DTEND%s')
    dtend = property(get_dtend, set_dtend)

    def get_summary(self):
        return self.get_property('summary')
    def set_summary(self, value):
        self.set_property(value, 'summary', 'SUMMARY:%s')
    summary = property(get_summary, set_summary)

    def get_location(self):
        return self.get_property('location')
    def set_location(self, value):
        self.set_property(value, 'location', 'LOCATION:%s')
    location = property(get_location, set_location)

    def get_description(self):
        return self.get_property('description')
    def set_description(self, value):
        self.set_property(value, 'description', 'DESCRIPTION:%s')
    description = property(get_description, set_description)

    def get_status(self):
        return self.get_property('status')
    def set_status(self, value):
        self.set_property(value, 'status', 'STATUS:%s')
    status = property(get_status, set_status)

    def get_organizer(self):
        return self.get_property('organizer')
    def set_organizer(self, value):
        self.set_property(value, 'organizer', 'ORGANIZER%s')
    organizer = property(get_organizer, set_organizer)

    def parseline(self, real_lines, line, attachments, attach_write_func=None):
        if line.startswith('DTSTART'):
            value = line[len('DTSTART'):]
            self.dtstart = self.datetime_to_utc(value)
        elif line.startswith('DTEND'):
            value = line[len('DTEND'):]
            self.dtend = self.datetime_to_utc(value)
        elif line.startswith('UID:'):
            self.uid = line[len('UID:'):]
        elif line.startswith('X-GWRECORDID:'):
            self.gwrecordid = line[len('X-GWRECORDID:'):]
        elif line.startswith('DTSTAMP:'):
            utc = self.datetime_to_utc(line[len('DTSTAMP'):])
            if utc.startswith(':'):
                utc = utc[1:]
            self.dtstamp = utc
        elif line.startswith('SUMMARY:'):
            self.summary = line[len('SUMMARY:'):]
        elif line.startswith('LOCATION:'):
            self.location = line[len('LOCATION:'):]
        elif line.startswith('DESCRIPTION:'):
            self.description = line[len('DESCRIPTION:'):]
        elif line.startswith('STATUS:'):
            self.status = line[len('STATUS:'):]
        elif line.startswith('ORGANIZER'):
            self.organizer = ParametrizedValue(line[len('ORGANIZER'):])
        elif line.startswith('ATTENDEE'):
            self.attendees.append(ParametrizedValue(line[len('ATTENDEE'):]))
        elif line.startswith('ATTACH'):
            attach = ParametrizedValue(line[len('ATTACH'):])
            if attach.value.lower() == 'cid:...':
                for attachment in attachments:
                    attach = ParametrizedValue('')
                    filename = 'unnamed'
                    if attachment['filename']:
                        filename = attachment['filename']
                    if self.gwrecordid:
                        filename = os.path.join(self.gwrecordid, filename)
                    payload = attachment['payload']
                    attach.value = attach_write_func(filename, payload)
                    self.attachments.append(attach)
        else:
            # Don't add lines if we got a property: the line is
            # auto-added in the property setter
            self.lines.extend(real_lines)

    def datetime_to_utc(self, local):
        value = ParametrizedValue(local)
        if 'TZID' in value.params:
            # We got a localized time, search for the timezone definition
            # we extracted from the calendar and convert to UTC
            tzid = value.params['TZID']

            # Strip the possible quotes from the tzid
            tzid = tzid.translate(None, '"\'')

            tz = self.tzmap[tzid.lower()]
            dt = datetime.datetime.strptime(value.value, '%Y%m%dT%H%M%S')
            utc_dt = dt - tz.utcoffset(dt);
            value.value = utc_dt.strftime('%Y%m%dT%H%M%SZ')
            del value.params['TZID']
        elif not value.value.endswith('Z') and value.value.find('T') >= 0:
            # No time zone indication: assume it's local time
            dt = time.strptime(value.value, '%Y%m%dT%H%M%S')
            utc_dt = time.gmtime(time.mktime(dt))
            value.value = time.strftime('%Y%m%dT%H%M%SZ', utc_dt)

        return value.to_ical()

    def to_ical(self):
        attendees_lines = []
        attachments_lines = []
        for attendee in self.attendees:
            attendees_lines.append('ATTENDEE%s' % attendee)
        for attachment in self.attachments:
            attachments_lines.append('ATTACH%s' % attachment)
        return 'BEGIN:VEVENT\r\n%s\r\n%s\r\n%s\r\nEND:VEVENT\r\n' % (
                    '\r\n'.join(self.lines), '\r\n'.join(attendees_lines),
                    '\r\n'.join(attachments_lines))

    def __eq__(self, other):
        # Get the properties as a dictionary without lines numbers to compare them
        self_props = {}
        for prop in self.properties:
            self_props[prop] = self.properties[prop][0]

        other_props = {}
        for prop in other.properties:
            other_props[prop] = other.properties[prop][0]

        # We don't mind the order of the items in the dictionary in the comparison
        props_equal = set(self_props.items()) ^ set(other_props.items())
        attendees_equal = set(self.attendees) ^ set(other.attendees)
        return len(props_equal) == 0 and len(attendees_equal) == 0
