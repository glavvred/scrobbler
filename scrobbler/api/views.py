from time import time

from flask import Blueprint, redirect, request, url_for

from scrobbler import db
from scrobbler.api.consts import PONG, RADIO_HANDSHAKE, UPDATE_CHECK
from scrobbler.api.helpers import (api_response, authenticate, md5,
                                   parse_auth_request, parse_np_request, parse_scrobble_request)
from scrobbler.models import NowPlaying, Scrobble, Session, User

blueprint = Blueprint('api', __name__)


@blueprint.route('/', methods=['GET', 'POST'])
def handshake():
    handshake = request.args.get('hs')

    if handshake is None:
        return redirect(url_for('webui.index'))

    data = parse_auth_request(request.args)

    if not data:
        return api_response('BADREQUEST'), 400

    user = db.session.query(User).filter_by(username=data['username']).first()
    if not authenticate(user, data['timestamp'], data['auth']):
        return api_response('BADAUTH')

    session = db.session.query(Session).filter(Session.user_id == user.id).first()

    if session:
        session_id = session.session_id
    else:
        current_time = str(int(time()))
        session_id = md5(user.username + user.api_password + current_time)

        session = Session(user_id=user.id, session_id=session_id, session_time=current_time)
        db.session.add(session)
        db.session.commit()

    return api_response(
        'OK',
        session_id,
        'http://post.audioscrobbler.com:80/np_1.2',
        'http://post.audioscrobbler.com:80/protocol_1.2',
    )


@blueprint.route('/ass/pwcheck.php')
def password_check():
    data = parse_auth_request(request.args)
    if not data:
        return api_response('BADREQUEST'), 400

    user = db.session.query(User).filter_by(username=data['username']).first()
    if not authenticate(user, data['timestamp'], data['auth']):
        return api_response('BADPASSWORD')

    return api_response('OK')


@blueprint.route('/np_1.2', methods=['POST'])
def now_playing():
    data = parse_np_request(request.form)
    if not data:
        return api_response('BADREQUEST'), 400

    session = db.session.query(Session).filter(Session.session_id == data['session_id']).first()

    if session is None:
        return api_response('BADSESSION')

    np = db.session.query(NowPlaying).filter(NowPlaying.user_id == session.user_id)

    data.pop('session_id', None)

    if np.first() is None:
        np = NowPlaying(**data)
        db.session.add(np)
    else:
        np.update(data)

    db.session.commit()

    return api_response('OK')


@blueprint.route('/protocol_1.2', methods=['POST'])
def scrobble():
    session_id, scrobbles = parse_scrobble_request(request.form)
    if not session_id:
        return api_response('BADREQUEST'), 400

    session = db.session.query(Session).filter(Session.session_id == session_id).first()

    for data in scrobbles:
        scrobble = Scrobble(user_id=session.user_id, **data)
        db.session.add(scrobble)

    db.session.commit()

    return api_response('OK')


@blueprint.route('/1.0/rw/xmlrpc.php', methods=['POST'])
def xmlrpc():
    return PONG


@blueprint.route('/ass/upgrade.xml.php', methods=['GET', 'POST'])
def update_check():
    return UPDATE_CHECK


@blueprint.route('/radio/handshake.php')
def radio_handshake():
    return RADIO_HANDSHAKE