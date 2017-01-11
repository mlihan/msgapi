from pymongo import MongoClient
import os

mongodb_path = os.environ['MONGODB_URI']

client = MongoClient(mongodb_path)

celeb_collection = client.heroku_lsms3n9l.celebs

def addRecord(celeb_id, en_name, sex, country, image_url, local_name=None, zh_name=None,  age=None, message_id=None):
    record = {
    	'celeb_id':celeb_id,
    	'en_name':en_name,
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
    return celeb_collection.find_one({'celeb_id':int(celeb_id)})

def findRecordWithName(en_name):
    return celeb_collection.find_one({'en_name': name})

def updateImageWithId(celeb_id, image_url, image_id):
    return celeb_collection.update_one(
        {'celeb_id':int(celeb_id)}, 
        {'$set': {'image_url': image_url, 'image_id': image_id}}
    )