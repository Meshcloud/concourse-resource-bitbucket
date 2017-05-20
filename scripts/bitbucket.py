#!/usr/bin/env python

import sys
import json
import requests
from requests.auth import HTTPBasicAuth, AuthBase

ERROR_MAP = {
    403: "HTTP 403 Forbidden - Does your bitbucket user have rights to the repo?",
    404: "HTTP 404 Not Found - Does the repo supplied exist?",
    400: "HTTP 401 Unauthorized - Are your bitbucket credentials correct?"
}


class BitbucketException(Exception): pass


class BitbucketOAuth(AuthBase):
    """
        Adds the correct auth token for OAuth access to bitbucket.com
    """
    def __init__(self, access_token):
        self.access_token = access_token

    def __call__(self, r):
        r.headers['Authorization'] = "Bearer {}".format(self.access_token)
        return r


# Convenience method for writing to stderr. Coerces input to a string.
def err(txt):
    sys.stderr.write(str(txt) + "\n")


# Convenience method for pretty-printing JSON
def json_pp(json_object):
    if isinstance(json_object, dict):
        return json.dumps(json_object,
                   sort_keys=True,
                   indent=4,
                   separators=(',', ':')) + "\n"
    elif isinstance(json_object, str):
        return json.dumps(json.loads(json_object),
                   sort_keys=True,
                   indent=4,
                   separators=(',', ':')) + "\n"
    else:
        raise NameError('Must be a dictionary or json-formatted string')


def set_build_status(repo, commit_sha, state, key, name, url, description,
                     access_token, debug, driver, endpoint, username, password, verify_ssl):

    post_url = ''

    # Construct the URL and JSON objects
    if driver == 'Bitbucket Server':
        post_url = "{endpoint}/rest/build-status/1.0/commits/{commit}".format(
            endpoint=endpoint.rstrip('/'),
            commit=commit_sha
        )

        # Squelch the nanny message if we disabled SSL
        if verify_ssl is False:
            requests.packages.urllib3.disable_warnings()
            if debug:
                err("SSL warnings disabled\n")
    elif driver == 'Bitbucket Cloud':
        post_url = "https://api.bitbucket.org/2.0/repositories/{repo}/commit/{commit}/statuses/build".format(
            repo=repo,
            commit=commit_sha
        )
    else:
        err("Invalid driver, must be: Bitbucket Server or Bitbucket Cloud")
        exit(1)

    data = {
        "state": state,
        "key": key,
        "name": name,
        "url": url,
        "description": description
    }

    if driver == 'Bitbucket Cloud':
        r = requests.post(
            post_url,
            auth=BitbucketOAuth(access_token),
            json=data
        )
    elif driver == 'Bitbucket Server':
        r = requests.post(
            post_url,
            auth=HTTPBasicAuth(username, password),
            verify=verify_ssl,
            json=data
        )

    if debug:
        err("Request result: " + str(r))

    # Check status code. Bitbucket brakes rest a bit  by returning 200 or 201
    # depending on it's the first time the status is posted.
    if driver == 'Bitbucket Cloud':
        if r.status_code not in [200, 201]:
            try:
                msg = ERROR_MAP[r.status_code]
            except KeyError:
                msg = json_pp(r.json())

            raise BitbucketException(msg)
    elif driver == 'Bitbucket Server':
        if r.status_code not in [204]:
            try:
                msg = ERROR_MAP[r.status_code]
            except KeyError:
                msg = json_pp(r.json())

            raise BitbucketException(msg)


def request_access_token(client_id, secret, debug):
    r = requests.post(
        'https://bitbucket.org/site/oauth2/access_token',
        auth=HTTPBasicAuth(client_id, secret),
        data={'grant_type': 'client_credentials'}
        )

    if debug:
        err("Access token result: " + str(r) + str(r.content))

    if r.status_code != 200:
        try:
            msg = ERROR_MAP[r.status_code]
        except KeyError:
            msg = json_pp(r.json())

        raise BitbucketException(msg)

    return r.json()['access_token']
