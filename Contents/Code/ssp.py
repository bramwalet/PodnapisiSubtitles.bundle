import xmlrpclib
from hashlib import md5, sha256

PODNAPISI_API = "http://ssp.podnapisi.net:8000"
PODNAPISI_STATIC_CONTENT = "http://www.podnapisi.net/static/podnapisi/"

class Response:
    Ok = 200
    InvalidCredentials = 300
    NoAuthorisation = 301
    InvalidSession = 302
    MovieNotFound = 400
    InvalidFormat = 401
    InvalidLanguage = 402
    InvalidHash = 403
    InvalidArchive = 404
    Unknown = -1    
        
class PodnapisiSspClient:
    
    def __init__(self, userAgent):
        self.server = xmlrpclib.ServerProxy(PODNAPISI_API)
        self.token = None
        self.userAgent = userAgent
    
    def resetToken(self):
        self.token = None
    
    def authenticate(self, username, password):
        if not self.token: 
            result = self.server.initiate(self.userAgent)
            if result['status'] != Response.Ok:
                Log.Error("XML-RPC: Initialize failed, status code: " + str(result['status']))
                return False
            else:
                Log.Debug("XML-RPC: Initiate succesful.")
                # TODO: set Language filters (server.setFilters())
    
            password = sha256(md5(password).hexdigest() + result['nonce']).hexdigest()
            self.token = result['session']
            result = self.server.authenticate(self.token, username, password)
            if result['status'] != Response.Ok:
                Log.Error("XML-RPC: Authentication failed, status code: %s", str(result['status']))
                self.token = None
                return False
            else:
                Log.Debug("XML-RPC: Authentication succesful.")
                return True
        else: 
            Log.Debug("XML-RPC: Already signed in")
            return True;
    
#     def searchSubtitle(self, hash):
#         self.
        
    def getSubtitleUrls(self, subtitleIds, retry=False):
        result = []
        response = self.server.download(self.token, subtitleIds);
        if response['status'] == Response.Ok: 
            if not response['names']:
                return None
            for subtitleName in response['names']:
                subtitleUrl = PODNAPISI_STATIC_CONTENT + subtitleName['filename']
                Log.Debug("XML-RPC: Adding subtitleUrl %s", subtitleUrl)
                result.append(subtitleUrl)
        elif response['status'] == Response.InvalidSession and not retry:
            Log.Warn("XML-RPC: Session invalid, retrying authentication.")
            self.authenticate();
            result = self.getSubtitleUrls(subtitleIds, True);
        

        return result