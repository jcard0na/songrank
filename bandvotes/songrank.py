# vim:set et ts=4 sw=4:
#
# Copyright (c) 2012 cozybit Inc.
#

import re
import logging
import os
import datetime
import json
import urllib

from google.appengine.ext import ndb
from google.appengine.api import namespace_manager
from google.appengine.api import users

import webapp2
import jinja2

from model import SongNode, Configuration, Bands
from notifications import send_notifications

VOTES_TO_GRADUATE=5

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def fuzzy_readable_time(delta):
    if not delta:
        return "never"
    if (delta.total_seconds() < 1):
        return "just now"
    if (delta.total_seconds() < 2):
        return str(delta.seconds) + " second ago"
    if (delta.total_seconds() < 60):
        return str(delta.seconds) + " seconds ago"
    elif delta.total_seconds() < 120:
        return str(delta.seconds / 60) + " minute ago"
    elif delta.total_seconds() < 3600:
        return str(delta.seconds / 60) + " minutes ago"
    elif delta.total_seconds() < 2 * 3600:
        return str(delta.seconds / 3600) + " hour ago"
    elif delta.total_seconds() < 24 * 3600:
        return str(delta.seconds / 3600) + " hours ago"
    elif delta.total_seconds() < 2 * 24 * 3600:
        return str(delta.days) + " day ago"
    else:
        return str(delta.days) + " days ago"

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            template = JINJA_ENVIRONMENT.get_template('create.html')
            self.response.write(template.render())
        else:
            self.redirect(users.create_login_url(self.request.uri))

class NewBand(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
        votes_to_graduate = self.request.get('votes_to_graduate')
        name = self.request.get('name')
        bandid = urllib.quote(name.replace(' ', '-').lower())
        if not name or not votes_to_graduate or Bands.get_by_id(bandid):
            msg = "Requested group exists already"
	else:
            msg = "New band created successfully"
            Bands(id=bandid).put()
            namespace_manager.set_namespace(bandid)
            conf = Configuration(id="singleton")
            conf.name = name
            conf.votes_to_graduate = int(votes_to_graduate)
            conf.put()

        template_values = {
            'bandid': bandid,
            'name': name,
            'votes_to_graduate': votes_to_graduate,
            'msg': msg 
        }

        template = JINJA_ENVIRONMENT.get_template('confirm.html')
        self.response.write(template.render(template_values))

class Comment(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        bandid = self.request.get('bandid')
        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        name = self.request.get('name')
        interpreter = self.request.get('interpreter')
        comment = self.request.get('comment')
        song = SongNode.get_by_id(name+interpreter)
        if not song:
            self.error(404)
            
        song.comments.append(comment + ' (' + user.nickname() + ')')
        song.put()
        song_url=urllib.quote('/' + bandid + '/song/' + song.name + '/' + song.interpreter)
        send_notifications(song,'http://' + self.request.host + song_url, 'comment', user)
        self.redirect(song_url)

class AddLink(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        bandid = self.request.get('bandid')
        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        name = self.request.get('name')
        interpreter = self.request.get('interpreter')
        link = self.request.get('link')
        song = SongNode.get_by_id(name+interpreter)
        if not song:
            self.error(404)
            
        song.links.append(link)
        song.put()
        song_url=urllib.quote('/' + bandid + '/song/' + song.name + '/' + song.interpreter)
        send_notifications(song,'http://' + self.request.host + song_url, 'link', user)
        self.redirect(song_url)

class Vote(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        bandid = self.request.get('bandid')
        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        conf = Configuration.get_by_id("singleton")
        if user not in conf.auth_users:
            logging.info("letting an unauthed users vote... for now")

        name = self.request.get('name').strip()
        interpreter = self.request.get('interpreter').strip()
        songid = name + interpreter
        song = SongNode.get_by_id(songid)
        if not song:
            song = SongNode(id=name+interpreter)
            song.name = name
            song.interpreter = interpreter
            song.vote_cnt = 0
            song.comments = [] 
            song.links = [] 
            song.votes = []
            song.graduated = False

            
        song_url=urllib.quote('/' + bandid + '/song/' + name + '/' + interpreter)
        unvote = self.request.get('undo', default_value=False)
        if user not in song.votes and not unvote:
            logging.info(str(user) + ' voted for ' + song.name)
            song.votes.append(user)
            song.vote_cnt += 1
            send_notifications(song,'http://' + self.request.host + song_url, 'vote', user)
        elif user in song.votes and unvote == 'true':
            logging.info(str(user) + ' unvoted for ' + song.name)
            song.votes.remove(user)
            song.vote_cnt -= 1
            send_notifications(song,'http://' + self.request.host + song_url, 'unvote', user)
        else:
            logging.error(str(user) + ' failed to vote/unvote for ' + song.name)
            return

        song.graduated = song.vote_cnt >= VOTES_TO_GRADUATE
        song.put()
        self.redirect(song_url)

class MultiVote(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        bandid = self.request.get('bandid')
        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        conf = Configuration.get_by_id("singleton")
        if user not in conf.auth_users:
            logging.info("letting an unauthed users vote... for now")

        votes = self.request.get_all('votes')
        for songid in votes:
            logging.info('songid:' + songid + 'len: ' + str(len(songid)))
            song = SongNode.get_by_id(songid)
            song_url=urllib.quote('/' + bandid + '/song/' + song.name + '/' + song.interpreter)
            if user not in song.votes:
                send_notifications(song,'http://' + self.request.host + song_url, 'vote', user)
                song.votes.append(user)
                song.vote_cnt += 1
                song.graduated = song.vote_cnt >= VOTES_TO_GRADUATE
                song.put()

        self.redirect('/' + bandid + '/thanks')

class Ranking(webapp2.RequestHandler):
    def get(self, bandid):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        conf = Configuration.get_by_id("singleton")
        if user not in conf.users:
            conf.users.append(user)
            # TODO: For now users are authenticated by default.  This should
            # probably be a configuration parameter.
            conf.auth_users.append(user)
            conf.put()
        ranking_query = SongNode.query().order(-SongNode.vote_cnt)
        ranking_query = ranking_query.filter(SongNode.vote_cnt < conf.votes_to_graduate)
        songs = ranking_query.fetch(50)

        template_values = {
            'is_admin': conf.admin == user,
            'songs': songs,
            'band_name': conf.name,
            'bandid': bandid,
            'logout_uri': users.create_login_url(self.request.uri),
            'votes_to_graduate': conf.votes_to_graduate
        }

        template = JINJA_ENVIRONMENT.get_template('ranking.html')
        self.response.write(template.render(template_values))

class Repertoire(webapp2.RequestHandler):
    def get(self, bandid):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return
        
        ranking_query = SongNode.query().order(-SongNode.vote_cnt)
        ranking_query = ranking_query.filter(SongNode.vote_cnt >= VOTES_TO_GRADUATE)
        songs = ranking_query.fetch()

        template_values = {
            'songs': songs,
            'bandid': bandid,
            'logout_uri': users.create_login_url(self.request.uri)
        }

        template = JINJA_ENVIRONMENT.get_template('repertoire.html')
        self.response.write(template.render(template_values))

class SongDetails(webapp2.RequestHandler):
    def get(self, bandid, name, interpreter):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        song = SongNode.get_by_id(name+interpreter)
        if not song:
            logging.error("Cant find song id = " + name + interpreter)
            self.error(404);
            return

        template_values = {
            'song': song,
            'last_update': fuzzy_readable_time(datetime.datetime.now() - song.last_update),
            'bandid': bandid,
            'user_has_voted': user in song.votes
        }

        template = JINJA_ENVIRONMENT.get_template('song.html')
        self.response.write(template.render(template_values))

class Thanks(webapp2.RequestHandler):
    def get(self, bandid):

        template_values = {
            'bandid': bandid,
        }

        template = JINJA_ENVIRONMENT.get_template('thanks.html')
        self.response.write(template.render(template_values))

class Purge(webapp2.RequestHandler):
    def get(self, bandid):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

        ranking_query = SongNode.query()
        ranking_query = ranking_query.filter(SongNode.graduated == False)
        week_old = datetime.datetime.now() - datetime.timedelta(days=7)
        ranking_query = ranking_query.filter(SongNode.last_update < week_old)
        stale_songs = ranking_query.fetch(keys_only=True)
        ndb.delete_multi(stale_songs)

        ranking_query = SongNode.query()
        ranking_query = ranking_query.filter(SongNode.vote_cnt == 0)
        abandoned_songs = ranking_query.fetch(keys_only=True)
        ndb.delete_multi(abandoned_songs)
        self.response.write("Purge successful")

class Invite(webapp2.RequestHandler):
    def get(self, bandid):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return

class Config(webapp2.RequestHandler):
    ''' Admin can change configuration parameters.  Can see users accessing the
        system and strip voting rights
    '''
    def get(self, bandid):
        user = users.get_current_user()
        if not user:
            self.redirect(users.create_login_url(self.request.uri))

        logging.info('bandid: ' + bandid)
        try:
            namespace_manager.set_namespace(bandid)
        except:
            self.error(400);
            return
        
        conf = Configuration.get_by_id("singleton")

        if conf.admin == None:
            conf.admin = user
            conf.put()

        if conf.admin != user:
            self.error(401);
            return

        template_values = {
            'admin': conf.admin,
            'users': conf.users,
            'auth_users': conf.auth_users,
            'bandid': bandid,
        }

        template = JINJA_ENVIRONMENT.get_template('config.html')
        self.response.write(template.render(template_values))

application = webapp2.WSGIApplication([
    (r'/', MainPage),
    (r'/new', NewBand),
    (r'/vote', Vote),
    (r'/multivote', MultiVote),
    (r'/comment', Comment),
    (r'/link', AddLink),
    (r'/(.*)/thanks', Thanks),
    (r'/(.*)/ranking', Ranking),
    (r'/(.*)/purge', Purge),
    (r'/(.*)/invite', Invite),
    (r'/(.*)/results', Ranking),
    (r'/(.*)/repertoire', Repertoire),
    (r'/(.*)/config', Config),
    (r'/(.*)/song/(.*)/(.*)', SongDetails),
], debug=True)

