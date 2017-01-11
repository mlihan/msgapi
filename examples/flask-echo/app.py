# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from __future__ import unicode_literals

import os
import sys
import requests, json, configparser 
import celeb_db, compliment
import image_management 

from argparse import ArgumentParser
from watson_developer_cloud import VisualRecognitionV3

from random import randint
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, 
    ImageMessage, ImageSendMessage, ImagemapSendMessage,
    ButtonsTemplate, ConfirmTemplate, CarouselTemplate, CarouselColumn, 
    TemplateAction, PostbackTemplateAction, MessageTemplateAction, URITemplateAction, 
    BaseSize, URIImagemapAction, MessageImagemapAction, ImagemapArea,
    FollowEvent, JoinEvent, PostbackEvent
)

app = Flask(__name__)

# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
oa_id = os.getenv('OA_ID', None)
bluemix_api_key = os.getenv('BLUEMIX_API_KEY_1', None)
bluemix_classifier = os.getenv('BLUEMIX_CLASSIFIER_1', None)
cloudinary_cloud = os.getenv('CLOUDINARY_CLOUD', None)

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if bluemix_api_key is None:
    print('Specify BLUEMIX_API_KEY as environment variable.')
    sys.exit(1)
if oa_id is None:
    print('Specify OA_ID as environment variable')
    sys.exit(1)
if bluemix_classifier is None:
    print('Specify BLUEMIX_CLASSIFIER as environment variable')
    sys.exit(1)
if cloudinary_cloud is None:
    print('Specify CLOUDINARY_CLOUD as environment variable')
    sys.exit(1)

visual_recognition = VisualRecognitionV3('2016-05-20', api_key=bluemix_api_key)
line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)
config = configparser.ConfigParser()
config.read('locale.ini')
language = config.get('DEFAULT', 'language')
bluemix_index = 1

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(500)

    # analyze incoming events 
    for event in events:
        # For bluemix
        if isinstance(event, FollowEvent):
            # If user just added me, send welcome and confirm message
            app.logger.info('[EVENTLOG] FollowEvent: ' + str(event) )
            sendMessage = []
            sendMessage.append(createWelcomeMessage())
            sendMessage.append(createConfirmMessage(event.source.user_id))
        elif isinstance(event, JoinEvent):
            # If user invited me to a group, send confirm message
            app.logger.info('[EVENTLOG] JoinEvent: ' + str(event) )
            sendMessage = createConfirmMessage()
        elif isinstance(event, PostbackEvent):
            # For postback events
            app.logger.info('[EVENTLOG] PostbackEvent: ' + str(event) )
            sendMessage = analyzePostbackEvent(event)
        elif isinstance(event, MessageEvent) and isinstance(event.message, ImageMessage):
            # If user sends an image, save content
            app.logger.info('[EVENTLOG] MessageEvent(Image): ' + str(event) )
            image_url, sender_image_id = saveContentImage(event)
            # classify the image 
            classifiers = classifyImageMessage(image_url)

            # Check if no classifier found, send a text message
            if classifiers == 0:
                sendMessage = TextSendMessage(text='I\'m sorry, under maintainance. Please inform you-know-who if you see this message.')
            else:
                sendMessage = getMessageForClassifier(classifiers, sender_image_id)            
        else:
            continue

        line_bot_api.reply_message(event.reply_token, sendMessage)
    return 'OK'

# analyze postback action
def analyzePostbackEvent(event):
    data = str(event.postback.data)
    if 'action=tryme' in data:
        sendMessage = None
        if 'user_id' in data:
            # Use profile picture of user to classify
            user_id = data.split('&')[1].split('=')[1]
            pic_url = getProfilePictureUrl(user_id)
            image_url, image_id = image_management.upload(pic_url, 'profile_image')
            classifiers = classifyImageMessage(image_url)

            # Check if no classifier found, send a text message
            if classifiers == 0:
                sendMessage = TextSendMessage(text='I\'m sorry but your image is out of this world. Please try another image.')
            else:
                sendMessage = getMessageForClassifier(classifiers, image_id)            
        else:
            sendMessage = TextSendMessage(text='Please send me a picture of yourself.')
    elif 'action=agree' in data:
        sendMessage = []
        sendMessage.append(createImageMessage(data))
        if event.source.type == 'group':
            sendMessage.append(createConfirmMessage())
    elif 'action=disagree' in data:
        sendMessage = []
        sendMessage.append(createRedCarpet(data))
        if event.source.type == 'group':
            sendMessage.append(createConfirmMessage())
    return sendMessage

# Save image to cloudinary 
def saveContentImage(event):
    #app.logger.info(str(event))
    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        image_binary = message_content.content 

        # save image to cloudinary
        fp = open('temp_img', 'wb') 
        fp.write(image_binary)
        fp.close()
        image_url, image_id = image_management.upload('temp_img', 'user_image')
        return image_url, image_id
    except:
        app.logger.error('Unexpected error:' + response.text)
        return 'NG'

# Classify image in Bluemix
def classifyImageMessage(image_url):
    #initialize v3/classify
    threshold = config.get('DEFAULT', 'Bluemix_Threshold')
    response = None
    #call v3/classify
    try: 
        response = visual_recognition.classify(
        images_url=image_url,
        classifier_ids=[bluemix_classifier, 'default'], 
        threshold=threshold
        )
    except:
        app.logger.error('Unexpected errer please check limit.' + json.dumps(response))
        updateBluemixKey(((bluemix_index + 1) % 4) + 1)
        return 0
    app.logger.debug(json.dumps(response, indent=2))

    # check if a classifier is detected in the image
    if 'classifiers' in json.dumps(response):
        return response['images'][0]['classifiers']
    else:
        return 0

# Classify image in Bluemix
def hasFaceFromImageMessage(image_url):
    #call v3/detect_faces
    try: 
        response = visual_recognition.detect_faces(
        images_url=image_url
        )
    except:
        app.logger.error('Unexpected error please check limit.' + json.dumps(response))
        return 0
    app.logger.debug('detect_faces' + json.dumps(response, indent=2))

    # check if a classifier is detected in the image
    if 'gender' in json.dumps(response):
        first_face = response['images'][0]['faces'][0]
        gender = first_face['gender']['gender'].lower()
        age = 18
        try: 
            if gender == 'female':
                age = first_face['age']['min']
            else:
                age = first_face['age']['max'] 
        except:
            age = first_face['age']['max']
        return gender, age
    else:
        return None, None

# Analyze classifiers first the return specific message 
def getMessageForClassifier(classifiers, sender_image_id=None):
    isCelebrity = len(classifiers) > 1
    sorted_list = sorted(classifiers[0]['classes'], key=lambda k:(-float(k['score'])))
    max_confidence = sorted_list[0]['score']
    image_url = 'https://res.cloudinary.com/{0}/image/upload/{1}.jpg'.format(cloudinary_cloud, sender_image_id)
    gender, age = hasFaceFromImageMessage(image_url)
    
    app.logger.debug('isCelebrity: {0} max_confidence: {1} gender: {2} age: {3}'.format(str(isCelebrity), str(max_confidence), str(gender), str(age)))

    # 1 a person and celebrity look alike, send a template message carousel
    if isCelebrity and gender is not None:
        app.logger.info('[MATCH FOUND]')
        updateBluemixKey(((bluemix_index + 1) % 4) + 1)
        return createMessageTemplate(sorted_list, gender, age, 3, sender_image_id)
    # 2 a celebrity lookalike but not a person
    elif isCelebrity:
        app.logger.info('[CELEB ONLY]')
        type_class = classifiers[1]['classes'][0]['class']
        celeb = celeb_db.findRecordWithId(classifiers[0]['classes'][0]['class'])
        return TextSendMessage(text='It looks more like a {0} to me. Please send a selfie to get better results.'.format(type_class))
    # TODO: 3 a person, call detect_face send a single template message, 
    elif isPerson:
        app.logger.info('[PERSON ONLY]')
        type_class = classifiers[0]['classes'][0]['class']
        return TextSendMessage(text='You don\'t look like any celebrities, but you look like a {0}. Please try another image.'.format(type_class))
        #call v3/detect_face
    # 4 others. send a text message
    else:
        type_class = classifiers[0]['classes'][0]['class']
        text = "Is that a {0}? If I'm mistaken, please take a clearer picture of yourself.".format(type_class)
        return TextSendMessage(text=text)

# Create a carousel message template if user looks like a celebrity
def createMessageTemplate(sorted_list, gender, age, max_index=2, sender_image_id=None):
    columns = []
    for index, celeb_class in enumerate(sorted_list):
        # stop creating after max_index
        if index == max_index:
            break

        # find celeb in DB
        celeb = celeb_db.findRecordWithId(celeb_class['class'])

        # skip celeb with different gender
        if gender != celeb['sex']:
            app.logger.debug('Skipping {0} because user gender is {1}'.format(celeb['en_name'], gender))
            max_index = max_index + 1 
            continue

        # compute score based on api and index
        score = computeScore(celeb_class['score'], index)
        
        app.logger.debug('Carousel index: {0} for {1} score: {2} age: {3}'.format(
            str(index), str(celeb['en_name']), str(score), str(age)))
        # use image with face centered
        celeb['image_url'] = celeb['image_url'][:45] + 'c_fill,g_face:center,h_340,w_512/' + celeb['image_url'][45:]
        title = 'Your picture looks like ' + celeb['local_name'] + ' (' + celeb['en_name'] + ')'
        temp = CarouselColumn(
            thumbnail_image_url=celeb['image_url'],
            title=title[:39],
            text='Score: ' + score,
            actions=[
                PostbackTemplateAction(
                    label='Agree 同意',
                    text='Agree',
                    data='action=agree&celebImg=' + str(celeb['image_id']) + '&senderImg=' + str(sender_image_id) + '&score=' + str(score) + '&age=' + str(age)
                ),
                PostbackTemplateAction(
                    label='Disagree 不同意',
                    text='Disagree',
                    data='action=disagree&senderImg=' + str(sender_image_id) + '&gender=' + gender + '&age=' + str(age)
                )
            ]
        )
        if index % 2 == 0:
            temp.actions.append(
                URITemplateAction(
                        label='Share to friends',
                        uri='line://nv/recommendOA/@' + oa_id
                    )
                )
        else:
            temp.actions.append(
                URITemplateAction(
                        label='Add me as a friend',
                        uri='line://oaMessage/@' + oa_id +'/hello'
                    )
                )
        columns.append(temp)

    carousel_template_message = TemplateSendMessage(
        alt_text='Wow! A celebrity look alike! Please check your smartphone',
        template=CarouselTemplate(columns=columns)
    )
    return carousel_template_message

# create a welcome message
def createWelcomeMessage(): 
    text_message = TextSendMessage(text=config.get(language, 'Welcome_Message'))
    return text_message

# create a confirm message
def createConfirmMessage(user_id=None):
    # if has user id
    data = 'action=tryme'
    if user_id is not None:
        data = data + '&user_id=' + user_id

    confirm_template_message = TemplateSendMessage(
        alt_text='Please check message on your smartphone',
        template=ConfirmTemplate(
            text='Do you want to know which celebrity you look like? 想知道您的LINE大頭照像那位明星嗎？',
            actions=[
                PostbackTemplateAction(
                    label='Yes! 想！',
                    text='Yes!',
                    data=data
                ),
                MessageTemplateAction(
                    label='About Me',
                    text='I\'m a bot that searches for a celebrities who look like you. Try and send me a picture! 你有明星臉嗎？快上傳自拍照，狗仔隊馬上為你揭曉！'
                )
            ]
        )
    )
    return confirm_template_message

# create a image map message
def createImageMessage(data):
    celeb_img_id = data.split('&')[1].split('=')[1]
    sender_img_id = data.split('&')[2].split('=')[1]
    score = data.split('&')[3].split('=')[1]
    age = data.split('&')[4].split('=')[1]
    url = 'https://res.cloudinary.com/' \
        '{0}/image/upload/c_fill,g_face:center,l_' \
        '{1},w_225,h_400,x_-128,y_-20/c_fill,g_face:center,l_' \
        '{2},w_256,h_400,x_128,y_-20/c_scale,g_south,h_100,l_logo_w_name/l_text:Verdana_35_bold:Your%20Age:%20' \
        '{3},co_rgb:990C47,y_155,g_north,y_10/result.jpg' \
        .format(cloudinary_cloud, celeb_img_id, sender_img_id, age)

    app.logger.debug('celeb_img_id:' + str(celeb_img_id) + ' sender_img_id:' + sender_img_id + ' score:' + score + ' url:' + url)
    template = ImageSendMessage(
        original_content_url=url,
        preview_image_url=url
    )
    return template

    # url = 'https://ucarecdn.com/85b5644f-e692-4855-9db0-8c5a83096e25/-/resize'
    # imagemap_message = ImagemapSendMessage(
    #    base_url=url,
    #    alt_text='Please check your smartphone',
    #    base_size=BaseSize(height=1040, width=1040),
    #    actions=[
    #        URIImagemapAction(
    #            link_uri='https://example.com/',
    #            area=ImagemapArea(
    #                x=0, y=0, width=520, height=1040
    #            )
    #        ),
    #        MessageImagemapAction(
    #            text='hello',
    #            area=ImagemapArea(
    #                x=520, y=0, width=520, height=1040
    #             )
    #         )
    #     ]
    # )

    # return imagemap_message

def createRedCarpet(data):
    # get data
    sender_img_id = data.split('&')[1].split('=')[1]
    gender = data.split('&')[2].split('=')[1]
    age = data.split('&')[3].split('=')[1]
    url = ''
    # setup url based on gender
    if gender == 'female':
        url = 'https://res.cloudinary.com/{0}/image/upload/c_thumb,' \
        'g_face:center,h_100,r_max,w_70/u_bradgelina,x_-20,y_290/v1484046371/' \
        '{1}.jpg'.format(cloudinary_cloud, sender_img_id)
    else:
        url = 'https://res.cloudinary.com/{0}/image/upload/c_thumb,' \
        'g_face:center,h_90,r_max,w_60/a_-10/u_bradgelina,x_110,y_310/v1484046371/' \
        '{1}.jpg'.format(cloudinary_cloud,sender_img_id)
    template = ImageSendMessage(
        original_content_url=url,
        preview_image_url=url
    )
    return template
# compute look alike score of a celebrity
def computeScore(json_score, index):
    magic_num = index * 5
    score = (json_score * 100) - magic_num
    if score >= 100:
        score = 99
    return str(round(score, 0))

# change env config for bluemix 
def updateBluemixKey(index):
    app.logger.info('BLUEMIX API update to ' + index)
    classifier = 'BLUEMIX_CLASSIFIER_' + str(index)
    bluemix_classifiers = os.getenv(classifier, None)
    api_key = 'BLUEMIX_API_KEY_' + str(index)
    bluemix_api_key = os.getenv('BLUEMIX_API_KEY', None)

# get picture url of a profile
def getProfilePictureUrl(user_id):
    try:
        profile = line_bot_api.get_profile(user_id)
        return profile.picture_url
    except:
        app.logger.error('Unexpected error found: ' + + sys.exc_info()[0])

if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, host='0.0.0.0', port=int(options.port))
