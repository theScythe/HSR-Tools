#!/usr/bin/env python
# coding=utf-8

import sys
import argparse
import requests
from BeautifulSoup import BeautifulSoup
from urllib2 import HTTPError
from config import auth
from xml.dom.minidom import Document

# Parse arguments
parser = argparse.ArgumentParser(
    description='Query the HSR timetable.',
    epilog='Disclaimer: This is no official HSR app. The correctness \
            of the data is not guaranteed.')
parser.add_argument('day',
        choices=['mo', 'di', 'mi', 'do', 'fr'],
        help='day of the week')
parser.add_argument('-v', '--verbose',
        action='store_true',
        help='show lessons without lectures')
parser.add_argument('-x', '--xml',
        action='store_true',
        help='output to xml')
args = parser.parse_args()


# Get user credentials
username, password = auth.userinfo()


# Start session
with requests.session() as s:

    print 'Logging in...'

    # Get state data
    login_page = s.get('https://unterricht.hsr.ch/Login.aspx').read()
    soup = BeautifulSoup(login_page)
    viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
    eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']

    # Log in
    data = {
        '__VIEWSTATE': viewstate,
        '__EVENTVALIDATION': eventvalidation,
        'tbUserName': username,
        'tbPassword': password,
        'btnLogin': 'Login',
    }
    login_request = s.post('https://unterricht.hsr.ch/Login.aspx', data=data)

    # Get timetable
    stundenplan = s.get('https://unterricht.hsr.ch/Stundenplan/StundenplanAnsicht/StundenplanAnsicht.aspx')
    try:
        stundenplan.raise_for_status()
        print 'Login successful.'
    except HTTPError:
        print 'Login failed.'
        sys.exit(-1)

    # Get html table
    soup = BeautifulSoup(stundenplan.read())
    table = soup.find('table', {'id': 'ctl00_contentPlaceHolder_StundenplanControl_table'})
    rows = table.findAll('tr')

    # Prepare data structure
    days = tuple(field.text for field in rows[0].findAll('th')[1:])
    times = []
    data = dict((day, []) for day in days)

    # Fill data into dictionary
    print 'Fetching data...'
    for row in rows[1:]:
        times.append(row.find('th').text)
        for i, field in enumerate(row.findAll('td')):
            d = data[days[i]]
            if not field.text:
                # Yay, no lecture!
                d.append(None)
            else:
                field_info = {}
                for info in field.findAll('span'):
                    key = info['id'].rsplit('_', 1)[-1]
                    field_info[key] = info.text
                d.append(field_info)

    # Data is now ready to be queried.
    try:
        key = filter(lambda d: d[:2].lower() == args.day, days)[0]
    except IndexError:
        print 'Day "%s" not found in data.' % args.day
        sys.exit(-1)
    msg = 'Timetable for %s:' % key
    print '-'*len(msg)

    if args.xml:
      doc = Document()
      root = doc.createElement('timetable')
      root.setAttribute('owner', username)
      doc.appendChild(root)
      day = doc.createElement('day')
      day.setAttribute('key',key)
      root.appendChild(day)
      for time, subj in zip(times, data[key]):
          if subj:
              lesson = doc.createElement("lesson")
              lesson.setAttribute('time','%s-%s:' % (time[:5], time[5:10]))
              lesson.setAttribute('lecturer',subj['lblDozent'])
              lesson.setAttribute('room',subj['lblRaum'])
              text = doc.createTextNode(subj['lblKuerzel'])
              lesson.appendChild(text)
              day.appendChild(lesson)
          else: # TODO: should we consider the verbose flag here?
              lesson = doc.createElement("lesson")
              lesson.setAttribute('time','%s-%s:' % (time[:5], time[5:10]))
              text = doc.createTextNode('-')
              lesson.appendChild(text)
              day.appendChild(lesson)

      print doc.toprettyxml(indent='  ')
    else:
      print msg
      for time, subj in zip(times, data[key]):
          if subj:
              print '%s-%s:' % (time[:5], time[5:10]),
              print '%s @ %s [%s]' % (subj['lblKuerzel'], subj['lblRaum'], subj['lblDozent'])
          elif args.verbose:
              print '%s-%s:' % (time[:5], time[5:10]),
              print '-'

