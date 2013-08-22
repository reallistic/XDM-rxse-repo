__version_info__ = (1,1,1)
__version__ = '1.1.1'

from lib import requests
import json
import urllib
import httplib
from collections import defaultdict
api_key = '24e80eb914d9be7c19392358d24a39dc'
api_uri = 'http://ws.audioscrobbler.com/2.0/?api_key=%s' % api_key
#&method=album.search&album=believe'

class LastfmAPIError(Exception):
    """Root Exception class for Discogs API errors."""
    pass

class HTTPError(DiscogsAPIError):
    """Exception class for HTTP(lib) errors."""
    def __init__(self, code):
        self.code = code
        self.msg = httplib.responses[self.code]

    def __str__(self):
        return "HTTP status %i: %s." % (self.code, self.msg)


class PaginationError(LastfmAPIError):
    """Exception class for issues with paginated requests."""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class APIBase(object):
    def __init__(self):
        self._cached_response = None
        self._params = {}

    def __str__(self):
        return '<%s "%s">' % (self.__class__.__name__, self._id)

    def __repr__(self):
        return self.__str__().encode('utf-8')

    def _clear_cache(self):
        self._cached_response = None

    @property
    def _response(self):
        if not self._cached_response:
            self._cached_response = requests.get(self._uri, params=self._params)

        return self._cached_response

    @property
    def _uri_name(self):
        return self.__class__.__name__.lower()
    
    @property
    def _apibase(self):
        if self._uri_name == 'results':
            return 'album.search'

        elif self._uri_name == 'artist':
            if self._params["topalbums"]:
                del self._params["topalbums"]
                return 'artist.topalbums'

            return 'artist.getinfo'

        elif self._uri_name == 'album':
            return 'album.getinfo'
    
    @property
    def _uri(self):
        return '%s&method=%s' % (api_uri, self._apibase)

    @property
    def data(self):
        if self._response.content and self._response.status_code == 200:
            release_json = json.loads(self._response.content)
            return release_json.get('lfm').get(self._uri_name)
        else:
            status_code = self._response.status_code
            raise HTTPError(status_code)

def _parse_credits(extraartists):
    """
    Parse release and track level credits
    """
    _credits = defaultdict(list)
    for artist in extraartists:
        role = artist.get('role')
        tracks = artist.get('tracks')

        artist_dict = {'artists': Artist(artist['name'], anv=artist.get('anv'))}

        if tracks:
            artist_dict['tracks'] = tracks

        _credits[role].append(artist_dict)
    return _credits

def _class_from_string(api_string):
    class_map = {
            'album': Album,
            'artist': Artist
    }

    return class_map[api_string]

class Artist(APIBase):
    def __init__(self, name, anv=None):
        self._id = name
        self._aliases = []
        self._namevariations = []
        self.albums = []
        self._anv = anv or None
        APIBase.__init__(self)
        self._params['artist'] = self._id

    def __str__(self):
        return '<%s "%s">' % (self.__class__.__name__, self._anv + '*' if self._anv else self._id)

    @property
    def name(self):
        return self._id

    @property
    def anv(self):
        return self._anv

    @property
    def albums(self):
        # TODO: Implement fetch many release IDs
        #return [Release(r.get('id') for r in self.data.get('releases')]
        if not self._albums:
            self._params.update({'topalbums': '1'})
            self._clear_cache()

            for r in self.data.get('topalbums', []):
                self._albums.append(_class_from_string(r['type'])(r.get('name'), self.id))
        return self._albums
        

class Album(APIBase):
    def __init__(self, id, art):
        self._id = id
        self._artist = None
        self._credits = None
        self._tracklist = []
        APIBase.__init__(self)
        self._params['album'] = urllib.quote_plus(unicode(self._id).encode('utf-8'))
        self._params['artist'] = art

    @property
    def artist(self):
        if not self._artist:
            self._artist = self.data.get('artist').get('name')
        return self._artist

    #not used
    
    @property
    def credits(self):
        if not self._credits:
            self._credits = _parse_credits(self.data.get('extraartists', []))
        return self._credits

    @property
    def tracklist(self):
        if not self._tracklist:
            for track in self.data.get('tracks', []):
                artists = []
                track['extraartists'] = _parse_credits(track.get('extraartists', []))
                artists.append(Artist(track.get('artist').get('name'), anv=track.get('artist').get('name')))
                track['artists'] = artists
                track['type'] = 'Track' if track.get('rank') else 'Index Track'
                self._tracklist.append(track)
        return self._tracklist

    @property
    def title(self):
        return self.data.get('name')

class Search(APIBase):
    def __init__(self, query, page=1):
        self._id = query
        self._results = {}
        self._exactresults = []
        self._page = page
        APIBase.__init__(self)
        self._params['q'] = self._id
        self._params['page'] = self._page

    def _to_object(self, result):
        id = result.get('name')
        return _class_from_string(result['type'])(id, result.get('artist'))

    @property
    def _uri(self):
        return '%s/%s' % (api_uri, self._uri_name)

    @property
    def exactresults(self):
        if not self.data:
            return []

        if not self._exactresults:
            for result in self.data.get('exactresults', []):
                self._exactresults.append(self._to_object(result))
        return self._exactresults

    def results(self, page=1):
        page_key = 'page%s' % page

        if page != self._page:
            if page > self.pages:
                raise PaginationError('Page number exceeds maximum number of pages returned.')
            self._params['page'] = page
            self._clear_cache()

        if not self.data:
            return []

        if page_key not in self._results:
            self._results[page_key] = []
            for result in self.data.get('searchresults').get('results'):
                self._results[page_key].append(self._to_object(result))

        return self._results[page_key]

    @property
    def resultsperpage(self):
        if not self.data:
            return 0
        return int(self.data.get('results').get('opensearch:itemsPerPage', 0))

    @property
    def numresults(self):
        if not self.data:
            return 0
        return int(self.data.get('results').get('opensearch:totalResults', 0))
    
    #overwrite so that it returns results
    @property
    def _uri_name(self):
        return 'results'

    @property
    def pages(self):
        if not self.data:
            return 0
        return (self.numresults / self.resultsperpage) + 1

