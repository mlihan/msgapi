from pymongo import MongoClient
import os

mongodb_path = os.environ['MONGODB_URI']

client = MongoClient(mongodb_path)

celeb_collection = client.heroku_lsms3n9l.celebs

def addRecord(celeb_id, en_name, sex, country, image_url, local_name=None, zh_name=None,  age=None, message_id=None):
    record = {
    	'celeb_id':celeb_id,
    	'name_id':name_id,
    	'local_name':local_name, 
    	'zh_name':zh_name, 
    	'sex':sex,
    	'age':age,
    	'country':country,
    	'image_url':image_url,
    	'message_id':message_id
    }
    celeb_collection.insert_one(record)

def findRecordWithId(celeb_id):
    return image_collection.find({'celeb_id':celeb_id})

def findImageWithName(en_name):
    return image_collection.find({'en_name': name})