# vim:set et ts=4 sw=4:
#
# Copyright (c) 2012 cozybit Inc.
#

import logging
import urllib

from google.appengine.ext import ndb
from google.appengine.api import namespace_manager
from google.appengine.api import users
from google.appengine.api import mail

from model import SongNode

action_messages = {
    'vote' : 'voted on',
    'unvote' : 'unvoted on',
    'comment' : 'commented on',
    'link' : 'added a link to',
}

def send_notifications(song, url, action, actor):
    voters = song.votes
    for user in voters:
        if user.user_id() == actor.user_id():
            continue
        sender="Bandvotes Admin <javier@cozybit.com>"
        to=user.nickname() + " <" + user.email() + ">"
        subject="Bandvotes activity notification"
        body="""
Dear %s:

%s %s %s, a song you have voted for.
Check it out here: %s

Bandvotes team


To unsubscribe from these messages... bug the administrator to implement that feature.
""" % (user.nickname(), actor.nickname(), action_messages[action], song.name, url)
        mail.send_mail(sender=sender,
                      to=to,
                      subject=subject,
                      body=body)
	logging.info(body)
