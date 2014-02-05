from google.appengine.ext import ndb

class SongNode(ndb.Model):
    """Models nominated song"""
    name = ndb.StringProperty()
    interpreter = ndb.StringProperty()
    votes = ndb.UserProperty(repeated=True)
    vote_cnt = ndb.IntegerProperty()
    last_update = ndb.DateTimeProperty(auto_now=True)
    comments = ndb.StringProperty(repeated=True)
    links = ndb.StringProperty(repeated=True)
    graduated = ndb.BooleanProperty()
