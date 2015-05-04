 #!/usr/bin/python
###########################################################################
#          (C) Vrije Universiteit, Amsterdam (the Netherlands)            #
#                                                                         #
# This file is part of AmCAT - The Amsterdam Content Analysis Toolkit     #
#                                                                         #
# AmCAT is free software: you can redistribute it and/or modify it under  #
# the terms of the GNU Affero General Public License as published by the  #
# Free Software Foundation, either version 3 of the License, or (at your  #
# option) any later version.                                              #
#                                                                         #
# AmCAT is distributed in the hope that it will be useful, but WITHOUT    #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or   #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public     #
# License for more details.                                               #
#                                                                         #
# You should have received a copy of the GNU Affero General Public        #
# License along with AmCAT.  If not, see <http://www.gnu.org/licenses/>.  #
###########################################################################

from __future__ import unicode_literals, print_function, absolute_import


from lxml import html
import datetime, sys, urllib2, re, argparse
from amcatclient.amcatclient import AmcatAPI

import logging
log = logging.getLogger(__name__)

INDEXURL = "%s/actueel/1/%s"
BASEURL = "https://zoek.officielebekendmakingen.nl/%s"

def readdate(date):
    if date == None:
        date = datetime.date.today()
    else:
        date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    return date

def getdatelist(fromdate, todate):
    adddate = readdate(fromdate)
    todate = readdate(todate)
    datelist = []
    while adddate <= todate:
        datelist.append(adddate)
        adddate += datetime.timedelta(days=1)
    return datelist

class OfficieleBekendmakingenScraper():
    """Downloads XML files of documents that are PUBLISHED (!) on the assigned date"""
    doctypelist = ['kamerstuk','handelingen','kamervragen_zonder_antwoord', 'kamervragen_aanhangsel','agenda','niet_dossierstuk']

    def __init__(self):
        args = self.ask_args()
        self.conn = AmcatAPI(args.host, args.username, args.password)
        self.project = args.project
        self.articleset_id = args.articleset_id
        self.datelist = getdatelist(args.fromdate, args.todate)

    def scrape(self):
        for date in self.datelist:
            print(date)
            articles = []
            for unit in self.get_units(date):
                for article in self.scrape_unit(unit):
                    articles.append(article)
            if len(articles) > 0:
                self.conn.create_articles(project=self.project, articleset=self.articleset_id, json_data = articles)
            else:
                print('No articles on {date}'.format(date=date))

    def getdoc(self, url):
        page = urllib2.urlopen(url)
        return html.parse(page).getroot()

    def get_units(self, date):
        existing_urls = []
        for page in self.get_pages(date):
            doc = self.getdoc(page)
            for arturl in set(a.get('href') for a in doc.cssselect('div.lijst > ul > li > a')):
                arturl = BASEURL % arturl
                yield(arturl.replace('html','xml'))

    def get_pages(self, date):
        for doctype in self.doctypelist:
            url = INDEXURL % (doctype, date.strftime('%d%m%Y'))
            print(BASEURL % url)
            doc = self.getdoc(BASEURL % url)

            pages = set(p.get('href') for p in doc.cssselect('div.paginering.boven > a'))
            pages.add(url)
            for page in pages:
                yield BASEURL % page

    def getNotesDict(self, xml, printit=False):
        notesdict = {}
        for noot in xml.cssselect('noot'):

            if 'nr' in [e.tag for e in noot]:
                print(noot.get('nr'))
                notesdict[noot.get('nr')] = noot.text_content().strip()
            elif not noot.get('nr') == None: notesdict[noot.get('nr')] = noot.text_content().strip()
            elif not noot.find('noot.lijst') == None:
                for nr, n in enumerate(noot.find('noot.lijst')):
                        notesdict[noot.find('noot.nr').text_content() + '.%s' % nr] = n.text_content()
            else:
                try: nootid = noot.find('noot.nr').text_content()
                except: nootid = noot.get('id').strip('n')
                try: notesdict[nootid] = noot.find('noot.al').text_content().strip()
                except: notesdict[nootid] = ''


        if printit == True:
            for note in notesdict: print(note, ': ', notesdict[note])
        return notesdict

    def traceNootRefNr(self, nootref, xml):
        if not nootref.get('nr') == None: return nootref.get('nr')

        for noot in xml.cssselect('noot'):
            if noot.get('id') == nootref.get('refid'):
                nootrefnr = noot.find('noot.nr').text_content()
                return nootrefnr

    def getMetaDict(self, xml, printit=False):
        try:
            url = xml.cssselect('meta')[0].get('content')
            meta = self.getdoc(url)
            metadict = dict((meta.get('name'), meta.get('content')) for meta in meta.cssselect('metadata'))
        except:
            metadict = dict((meta.get('name'), meta.get('content')) for meta in xml.cssselect('meta'))
            metadict.update(dict((meta.get('property'), meta.get('content')) for meta in xml.cssselect('meta')))
        if printit == True:
            for meta in metadict: print(meta, ': ', metadict[meta])
        return metadict

    def safeMetaGet(self, d, key):
        try: value = d[key]
        except:
            value = 'missing'
            log.warn('MISSING METADATA FOR %s' % key)
        return value

    def _scrape_unit(self, url):
        xml = self.getdoc(url)
        print(xml)
        return []

    def ask_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('host', help='AmCAT host to connect to (http://amcat.vu.nl')
        parser.add_argument('project')
        parser.add_argument('articleset_id')
        parser.add_argument('username')
        parser.add_argument('password')
        parser.add_argument('--fromdate', help='Date in format YYYY-MM-DD. Default is today')
        parser.add_argument('--todate', help='Date in format YYYY-MM-DD. Default is today')
        return parser.parse_args()

if __name__ == '__main__':
    s = OfficieleBekendmakingenScraper()
    s.scrape()

