#!/usr/bin/env python3
import argparse
import logging
import requests
import json
from get_tweepy import get_api, tweepy
from get_mongo_client import get_mongo_client


def add_user(screen_name):
    try:
        user = api.get_user(screen_name)
        update_user(user)
    except:
        logger.error('not found user: @{}'.format(screen_name))


def delete_user(screen_name):
    try:
        user = api.get_user(screen_name)
        db.users.delete_one({'_id': user.id})
        logger.info('delete user: {}(@{})'.format(user.name, user.screen_name))
    except:
        logger.error('not found user: @{}'.format(screen_name))


def save():
    update_users()
    user_ids = load_user_ids()
    for user_id in user_ids:
        save_user(user_id)


def update_user(user):
    db.users.update_one({'_id': user.id},
                        {'$set': {'meta.exists': True, 'data': user._json}},
                        upsert=True)
    logger.info('update user: {}(@{})'.format(user.name, user.screen_name))


def load_user_ids(exists=True, protected=False):
    return db.users.find({
        'meta.exists': exists,
        'data.protected': protected,
    }).distinct('_id')


def update_users():
    user_ids = load_user_ids(protected=True)
    for user_id in user_ids:
        try:
            user = api.get_user(user_id=user_id)
            update_user(user)
        except:
            logger.info('save: user not found: {}'.format(user_id))
            db.users.update_one({'_id': user_id},
                                {'$set': {'meta.exists': False}},
                                upsert=True)


def save_user(user_id):
    logger.info('save_user: {}'.format(user_id))
    for tweet in tweepy.Cursor(api.user_timeline, user_id=user_id, count=200).items():
        # if already exists in db, skip rests
        if db.tweets.find({'_id': tweet.id}).count():
            break
        db.tweets.update_one({'_id': tweet.id},
                            {'$set': {'data': tweet._json}},
                            upsert=True)
        logger.info('saving tweet: {}'.format(tweet.id))


def twisave():
    for tweet in db.tweets.find({'meta.twisave': {'$exists': False}}):
        # check if success of get
        url = 'https://tweetsave.com/api.php?mode=save&tweet={}'
        r = requests.get(url.format(tweet['_id']))
        if not r.ok:
            logger.error('twisave: cannot get api: {}'.format(r.reason))
            break

        # check safed by twisave
        r = json.loads(r.text)
        if 'errors' in r:
            logger.error('twisave: failed to save by twisave: {}'.format(r['errors']))
            break
        
        # flag success result
        db.tweets.update_one({'_id': tweet['_id']}, {'$set': {'meta.twisave': True}})
        logger.info('twisave: saved tweet: {}'.format(tweet['_id']))
        

if __name__ == '__main__':
    # args
    parser = argparse.ArgumentParser()
    parser.add_argument('subcommand', choices=[
        'add_user',
        'delete_user',
        'save',
        'twisave',
    ])
    parser.add_argument('-u', '--user')
    args = parser.parse_args()

    # twitter api
    api = get_api('sakuramochi_0')

    # mongodb client
    cli = get_mongo_client()
    db = cli.twive

    # logger
    logger = logging.getLogger('twive')
    logging.basicConfig(level=logging.INFO)

    if args.subcommand == 'add_user':
        if args.user:
            add_user(args.user)
        else:
            parser.print_help()
    elif args.subcommand == 'delete_user':
        if args.user:
            delete_user(args.user)
        else:
            parser.print_help()
    elif args.subcommand == 'save':
        save()
    elif args.subcommand == 'twisave':
        twisave()
