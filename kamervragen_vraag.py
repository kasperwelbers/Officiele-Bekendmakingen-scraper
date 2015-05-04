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

import datetime, sys, urllib, urllib2, re
    
import logging
log = logging.getLogger(__name__)

from officiele_bekendmakingen import OfficieleBekendmakingenScraper

def adhocDatefix(datestring):
    datestring = datestring.replace('-02-31','-03-03').replace('-02-30','-03-02').replace('20090', '2009')
    return datestring
        
class KamervragenVraagScraper(OfficieleBekendmakingenScraper):
    doctypelist = ['kamervragen_zonder_antwoord']
    medium_name = "Kamervraag"

    def getVraag(self, bodypart, xml):
        try: nr = bodypart.find('nummer').text_content()
        except:
            try: nr = bodypart.find('nr').text_content()
            except: nr = 'missing'

        nr = nr.replace('Vraag', '').strip()
            
        vraag = ' '.join([al.text_content().replace('\n', ' ').replace('\r','').strip() for al in bodypart.cssselect('al')])
        for nootref in bodypart.cssselect('nootref'):
            vraag += " (Noot %s)" % self.traceNootRefNr(nootref, xml)
            
        if not nr == 'missing': return "Vraag %s:\n%s" % (nr, vraag)
        else: return vraag

    def getBody(self, xml):
        body = ''
        notesdict = self.getNotesDict(xml, printit=False)
    
        try: bodyparts = xml.cssselect('vragen')[0].getchildren()
        except: bodyparts = xml.cssselect('kamervragen')[0].getchildren()

        for bodypart in bodyparts:
            if bodypart.tag in ['omschr', 'kamervraagomschrijving']:               
                body += bodypart.text_content().replace('\n',' ').replace('\r','') + '\n'
            elif bodypart.tag == 'vraag':
                if bodypart.getchildren()[0].tag == 'tussenkop':
                    body += "\n%s\n" % bodypart.getchildren()[0].text_content()
                else: body += "\n%s\n" % self.getVraag(bodypart, xml)
            elif bodypart.tag in ['toelicht']:
                body += '\n' + bodypart.text_content().replace('\n',' ').replace('\r','').replace('Toelichting:', 'Toelichting:\n') + '\n'
            elif bodypart.tag == 'kamervraagopmerking': body += '\n' + bodypart.text_content().replace('\n',' ').replace('\r','').replace('Mededeling','Mededeling:\n') + '\n'
            elif bodypart.tag in ['titel','vraagnummer','noot','kamervraagkop','kamervraagnummer']: None
            else:
                print('\n\n\n\n',bodypart)
                
        for nr in sorted(notesdict):
            noteref1, noteref2, noteref3 = "%s%s" % (nr, notesdict[nr]), "%s %s" % (nr, notesdict[nr]), "%s  %s" % (nr, notesdict[nr])
            if notesdict[nr] in body: body = body.replace(noteref1, ' (Noot %s)' % nr).replace(noteref2, ' (Noot %s)' % nr).replace(noteref3, ' (Noot %s)' % nr)
            body += "\nNoot %s: %s" % (nr, notesdict[nr])
                        
        return body
            
    def scrape_unit(self, url):

        try: xml = self.getdoc(url)
        except:
            log.warn("COULD NOT FIND XML FOR %s" % url) 
            return
            #return []
        for e in xml.cssselect('div'):
            if e.get('id') == 'main-column':
                if 'Deze publicatie zal waarschijnlijk over enkele werkdagen ook als webpagina' in e.text_content():
                    log.warn('NOT YET PUBLISHED AS XML (needs to be retrieved later')
                    return

        url = url.replace('.xml','.html')
        metadict = self.getMetaDict(xml, printit=False)
        if len(metadict) == 0:
            log.warn("NO METADATA FOR %s. SKIPPING ARTICLE (to be retrieved after officiele bekendmakingen finalizes it)" % url) 
            return
            #return []

        section = self.safeMetaGet(metadict,'OVERHEID.category')

        if 'DC.identifier' in metadict: document_id = metadict['DC.identifier']
        else: document_id = metadict['dcterms.identifier']

        if document_id.count('-') == 1:
            #kamer = 'NA'
            if 'DC.creator' in metadict:
                if 'tweede' in  metadict['DC.creator'].lower(): kamer = 'tk'
                if 'eerste' in  metadict['DC.creator'].lower(): kamer = 'ek'
            else:
                if 'tweede' in  metadict['dcterms.creator'].lower(): kamer = 'tk'
                if 'eerste' in  metadict['dcterms.creator'].lower(): kamer = 'ek'
            document_id = document_id.replace('-','-%s-' % kamer)        
        print('document id:', document_id)

        author = self.safeMetaGet(metadict,'OVERHEIDop.indiener')
        if 'DC.type' in metadict: typevraag = metadict['DC.type']
        else: typevraag = metadict['dcterms.type']

        body = self.getBody(xml)
        headline = "document_id (%s)" % author

        try: datestring = adhocDatefix(metadict['OVERHEIDop.datumOntvangst'])
        except:
            datestring = adhocDatefix(metadict['OVERHEIDop.datumIndiening'])
            headline += " (publicatiedatum)"

        try: date = datetime.datetime.strptime(datestring, '%Y-%m-%d')
        except: date = datetime.datetime.strptime(datestring, '%d-%m-%Y')
        
        #print('--------------\n', document_id, typevraag, '\n', body, '\n\n') 
        print("SAVING: %s" % url)

        article = dict(headline=document_id, byline=typevraag, text=body, date=date, section=section, url=url, medium=self.medium_name)
        yield article


if __name__ == '__main__':
    s = KamervragenVraagScraper()
    s.scrape()

