#hdbits.org

import string, os, urllib, zipfile, re, copy
import ssp

PODNAPISI_MAIN_PAGE = "http://www.podnapisi.net"
PODNAPISI_SEARCH_PAGE = "http://www.podnapisi.net/en/ppodnapisi/search?sT=%d&"
PODNAPISI_API = "http://ssp.podnapisi.net:8000"
PODNAPISI_STATIC_CONTENT = "http://www.podnapisi.net/static/podnapisi/"

MOVIE_SEARCH = PODNAPISI_SEARCH_PAGE % 0
TV_SEARCH = PODNAPISI_SEARCH_PAGE % 1

OS_PLEX_USERAGENT = 'plexapp.com v9.0'
subtitleExt       = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']

langPrefs2Podnapisi = {'sq':'29','ar':'12','be':'50','bs':'10','bg':'33','ca':'53','zh':'17','cs':'7','da':'24','nl':'23','en':'2','et':'20','fi':'31','fr':'8','de':'5','el':'16','he':'22','hi':'42','hu':'15','is':'6','id':'54','it':'9','ja':'11','ko':'4','lv':'21','lt':'19','mk':'35','ms':'55','no':'3','pl':'26','pt':'32','ro':'13','ru':'27','sr':'36','sk':'37','sl':'1','es':'28','sv':'25','th':'44','tr':'30','uk':'46','vi':'51','hr':'38'}

mediaCopies = {}
sspClient = None 


def Start():
    global sspClient
    HTTP.CacheTime = 0
    HTTP.Headers['User-agent'] = OS_PLEX_USERAGENT
    Log.Debug("START  CALLED")
    sspClient = ssp.PodnapisiSspClient(OS_PLEX_USERAGENT)
    #sspClient.authenticate()

def ValidatePrefs():
    Log.Debug("Validate Prefs called.")
    username = Prefs["username"]
    password = Prefs["password"]
    if username and password:
        sspClient.resetToken()
        Log.Debug("Validating username and password.")
        if sspClient.authenticate(username, password):
            Log.Debug("Validation ok")
            return MessageContainer("Success", "Authentication successful.")
        else: 
            Log.Warn("Validation failed")
            return MessageContainer("Error","Username or password invalid.")
    else:
        return

#Prepare a list of languages we want subs for
def getLangList():
    langList = [Prefs["langPref1"]]
    if(Prefs["langPref2"] != "None"):
        langList.append(Prefs["langPref2"])
    return langList

def tvSearch(params, lang):
    Log.Debug("Params: %s" % urllib.urlencode(params))
    searchUrl = TV_SEARCH + urllib.urlencode(params)
    return simpleSearch(searchUrl, lang)

def movieSearch(params, lang):
    Log.Debug("Params: %s" % urllib.urlencode(params))
    searchUrl = MOVIE_SEARCH + urllib.urlencode(params)
    return simpleSearch(searchUrl, lang)

#Do a basic search for the filename and return all sub urls found
def simpleSearch(searchUrl, lang = 'eng'):
    subUrls = []
    searchUrl = searchUrl + "&sXML=1"
    Log.Debug("searchUrl: %s" % searchUrl)
    elemXml = XML.ElementFromURL(searchUrl)
    if len(elemXml.xpath("/results/subtitle")) > 0:    
        # XML-RPC download
        Log.Debug("Trying using XML-RPC method.")
        if sspClient.authenticate(Prefs["username"], Prefs["password"]):
            subtitleIds  = [ str(x) for x in elemXml.xpath("//id/text()") ]
            subUrls = sspClient.getSubtitleUrls(subtitleIds)
    
        if not subUrls:
            # web scraping
            Log.Debug("Falling back to web-scraping.")
            subUrls = scrapeDownloadLinks(elemXml.findall(".//url"))
    return subUrls
    
def scrapeDownloadLinks(urls):
    subUrls = []
    for url in urls:
        subPageUrl = url.text
        Log.Debug("Subpage: %s" % subPageUrl)
        pageElem = HTML.ElementFromURL(subPageUrl)
        downloadUrl = getDownloadUrlFromPage(pageElem)
        Log.Debug("DownloadURL: %s" % downloadUrl)
        subUrls.append(downloadUrl)
    return subUrls

def getDownloadUrlFromPage(pageElem):
    dlPart = pageElem.xpath("//div[@class='footer']//a[@class='button big download']/@href")[0]
    return PODNAPISI_MAIN_PAGE + dlPart

class SubInfo():
    def __init__(self, lang, url, sub, name):
        self.lang = lang
        self.url = url
        self.sub = sub
        self.name = name
        self.ext = string.split(self.name, '.')[-1]


def doSearch(data, lang, isTvShow):
    if(isTvShow):
        return tvSearch(data, lang)

    return movieSearch(data, lang)

def searchSubs(data, lang, isTvShow):

    subUrls = doSearch(data, lang, isTvShow)

    if not subUrls:
        Log.Debug("%d subs found - trying to remove release group" % len(subUrls))
        d = dict(data) # make a copy so that we still include release group for other searches
        del d['sR']
        subUrls = doSearch(d, lang, isTvShow)

    return subUrls

def getSubsForPart(data, isTvShow=True):
    siList = []
    for lang in getLangList():
        Log.Debug("Lang: %s,%s" % (lang, langPrefs2Podnapisi[lang]))
        data['sJ'] = langPrefs2Podnapisi[lang]

        subUrls = searchSubs(data, lang, isTvShow)

        for subUrl in subUrls:
            Log.Debug("Getting subtitle from: %s" % subUrl)
            zipArchive = Archive.ZipFromURL(subUrl)
            for name in zipArchive:
                Log.Debug("Name in zip: %s" % repr(name))
                if name[-1] == "/":
                    Log.Debug("Ignoring folder")
                    continue

                subData = zipArchive[name]
                si = SubInfo(lang, subUrl, subData, name)
                siList.append(si)

    return siList

def getReleaseGroup(filename):
    tmpFile = string.replace(filename, '-', '.')
    splitName = string.split(tmpFile, '.')
    group = splitName[-2]
    return group


        

class PodnapisiSubtitlesAgentMovies(Agent.Movies):
    name = 'Podnapisi Movie Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.imdb']

    def search(self, results, media, lang):
        Log.Debug("MOVIE SEARCH CALLED")
        mediaCopy = copy.copy(media.primary_metadata)
        uuid = String.UUID()
        mediaCopies[uuid] = mediaCopy
        results.Append(MetadataSearchResult(id = uuid, score = 100))

    def update(self, metadata, media, lang):
        Log.Debug("MOVIE UPDATE CALLED")
        mc = mediaCopies[metadata.id]
        for item in media.items:
            for part in item.parts:
                Log.Debug("Title: %s" % media.title)
                Log.Debug("Filename: %s" % part.file)
                Log.Debug("Year: %s" % mc.year)
                Log.Debug("Release group %s" % getReleaseGroup(part.file))

                data = {}
                data['sK'] = media.title
                data['sR'] = getReleaseGroup(part.file)
                data['sY'] = mc.year

                siList = getSubsForPart(data, False)

                for si in siList:
                    part.subtitles[Locale.Language.Match(si.lang)][si.url] = Proxy.Media(si.sub, ext=si.ext) 

        del(mediaCopies[metadata.id])


class PodnapisiSubtitlesAgentTvShows(Agent.TV_Shows):
    name = 'Podnapisi TV Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.thetvdb']

    def search(self, results, media, lang):
        Log.Debug("TV SEARCH CALLED")
        results.Append(MetadataSearchResult(id = 'null', score = 100))

    def update(self, metadata, media, lang):
        Log.Debug("TvUpdate. Lang %s" % lang)
        for season in media.seasons:
            for episode in media.seasons[season].episodes:
                for item in media.seasons[season].episodes[episode].items:
                    Log.Debug("show: %s" % media.title)
                    Log.Debug("Season: %s, Ep: %s" % (season, episode))
                    for part in item.parts:
                        Log.Debug("Release group: %s" % getReleaseGroup(part.file))
                        data = {}
                        data['sK'] = media.title
                        data['sTS'] = season
                        data['sTE'] = episode
                        data['sR'] = getReleaseGroup(part.file)

                        siList = getSubsForPart(data)

                        for si in siList:
                            part.subtitles[Locale.Language.Match(si.lang)][si.url] = Proxy.Media(si.sub, ext=si.ext) 
