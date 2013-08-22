# Author: Dennis Lutter <lad1337@gmail.com>
# URL: https://github.com/lad1337/XDM
#
# This file is part of XDM: eXtentable Download Manager.
#
#XDM: eXtentable Download Manager. Plugin based media collection manager.
#Copyright (C) 2013  Dennis Lutter
#
#XDM is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#XDM is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see http://www.gnu.org/licenses/.

from xdm.plugins import *

from libs import lastfm_client as lastfm
import re
lastfm.user_agent = '%s +http://xdm.lad1337.de' % common.getVersionHuman()


class Lastfm(Provider):
    version = "0.9"
    identifier = "de.lad1337.boxcar.lastfm"
    _tag = 'lastfm'
    single = True
    types = ['de.lad1337.music']
    _config = {'enabled': True,
               'search_range_select': 'master'}
    config_meta = {'plugin_desc': 'Information provider for music from http://www.last.fm'
                   }
                   
    search_range_select_map = {'master': {'t': 'Albums', 'c': ('Album',)}}

    def _search_range_select(self):
        out = {}
        for i, o in self.search_range_select_map.items():
            out[i] = o['t']
        return out

    def searchForElement(self, term='', id=0):

        self.progress.reset()
        #artist = lastfm.Artist('Aphex Twin')
        mediatype = MediaType.get(MediaType.identifier == 'de.lad1337.music')
        mtm = common.PM.getMediaTypeManager('de.lad1337.music')[0]

        if id:
            res = [lastfm.Artist(id)]
        else:
            log('LastFm searching for %s' % term)
            s = lastfm.Search(term)
            log.('Search api url: %s' % s._uri_params)
            res = s.results()

        fakeRoot = mtm.getFakeRoot(term)
        filtered = [album for album in res if album.__class__.__name__ in self.search_range_select_map[self.c.search_range_select]['c']]
        self.progress.total = len(res)

        for release in res:
            self.progress.addItem()
            #print '\n\n\n\n\n\n\n', release.data['formats'], release.data['status']
            self._createAlbum(fakeRoot, mediatype, release)

        return fakeRoot

    def _createAlbum(self, fakeRoot, mediaType, release):

        artist = release.artist
        artistName = re.sub(r' \(\d{1,2}\)$', '', artist.name)
        try:
            artistElement = Element.getWhereField(mediaType, 'Artist', {'id': artistName}, self.tag, fakeRoot)
        except Element.DoesNotExist:
            artistElement = Element()
            artistElement.mediaType = mediaType
            artistElement.parent = fakeRoot
            artistElement.type = 'Artist'
            artistElement.setField('name', artistName, self.tag)
            artistElement.setField('id', artistName, self.tag)
            artistElement.saveTemp()
        try:
            albumElement = Element.getWhereField(mediaType, 'Album', {'id': release.data['id']}, self.tag, artistElement)
            #print "we have" albumElement
        except Element.DoesNotExist:
            albumElement = Element()
            albumElement.mediaType = mediaType
            albumElement.parent = artistElement
            albumElement.type = 'Album'
            albumElement.setField('name', release.title, self.tag)
            albumElement.setField('year', release.data['year'], self.tag)
            albumElement.setField('id', release.data['id'], self.tag)
            if 'images' in release.data:
                for img in release.data['images']:
                    if img['uri']:
                        albumElement.setField('cover_image', img['uri'], self.tag)
                        break
            albumElement.saveTemp()
            for track in release.tracklist:
                trackElement = Element()
                trackElement.mediaType = mediaType
                trackElement.parent = albumElement
                trackElement.type = 'Song'
                trackElement.setField('title', track['title'], self.tag)
                trackElement.setField('length', track['duration'], self.tag)
                trackElement.setField('position', track['position'], self.tag)
                trackElement.saveTemp()
            albumElement.downloadImages()

    def getElement(self, id, element=None):
        mt = MediaType.get(MediaType.identifier == 'de.lad1337.music')
        mtm = common.PM.getMediaTypeManager('de.lad1337.music')[0]
        fakeRoot = mtm.getFakeRoot('%s ID: %s' % (self.tag, id))
        release = lastfm.Release(id)
        #print release
        #print master
        self._createAlbum(fakeRoot, mt, release)
        self._createAlbum(fakeRoot, mt, master)

        for ele in fakeRoot.decendants:
            if element is None:
                if ele.getField('id', self.tag) == id:
                    return ele
            else:
                """print ele.getField('id', self.tag), id, ele.getField('id', self.tag) == id
                print element.type, ele.type, element.type == ele.type
                print element.parent.getField('id', self.tag), ele.parent.getField('id', self.tag), element.parent.getField('id', self.tag) == ele.parent.getField('id', self.tag)
                print '#############'"""
                if ele.getField('id', self.tag) == id and element.type == ele.type and element.parent.getField('id', self.tag) == ele.parent.getField('id', self.tag):
                    return ele
        else:
            return False
