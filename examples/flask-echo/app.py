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
import celeb_db
import image_management 

from compliment import Compliment
from argparse import ArgumentParser
from watson_developer_cloud import VisualRecognitionV3

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
bluemix_api_key = os.getenv('BLUEMIX_API_KEY', None)

if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if bluemix_api_key is None:
    print('Specify BLUEMIX_API_KEY as environment variable.')
    sys.exit(1)

visual_recognition = VisualRecognitionV3('2016-05-20', api_key=bluemix_api_key)
line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)
config = configparser.ConfigParser()
config.read('locale.ini')
language = config.get('DEFAULT', 'language')

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

    # if event is MessageEvent and message is TextMessage, then check prefix
    for event in events:
        # For bluemix
        if isinstance(event, FollowEvent):
            # If user just added me, send welcome and confirm message
            sendMessage = []
            sendMessage.append(createWelcomeMessage())
            sendMessage.append(createConfirmMessage())
        elif isinstance(event, JoinEvent):
            # If user invited me to a group, send confirm message
            sendMessage = createConfirmMessage()
        elif isinstance(event, PostbackEvent):
            # For postback events
            sendMessage = analyzePostbackEvent(event)
        elif isinstance(event, MessageEvent) and isinstance(event.message, ImageMessage):
            # If user sends an image, save content
            image_url = saveContentImage(event)
            # classify the image 
            classifiers = classifyImageMessage(image_url)

            # After classification reply the following to user
            # 1 no classifier found, send a text message
            if classifiers == 0:
                app.logger.info('no classifier!!')
                sendMessage = TextSendMessage(text='I\'m sorry but your image is out of this world.')
                line_bot_api.reply_message(event.reply_token, sendMessage)
                return 'OK'

            isCelebrity = len(classifiers) > 1
            isPerson = 'person' in json.dumps(classifiers)
            
            app.logger.info('isCelebrity: ' + str(isCelebrity) + ' isPerson:' + str(isPerson))

            # 2 a person and celebrity look alike, send a template message carousel
            if isCelebrity and isPerson:
                sendMessage = createMessageTemplate('marc', classifiers)
            # 3 a celebrity lookalike but not a person
            elif isCelebrity:
                type_class = classifiers[0]['classes'][1]['class']
                celeb = celeb_db.findRecordWithId(classifiers[0]['classes'][0]['class'])
                sendMessage = TextSendMessage(text='Funny, that looks like my friend ' + celeb['local_name'] + ' but that is a ' + type_class)
            # TODO: 4 a person, call detect_face send a single template message, 
            elif isPerson:
                type_class = classifiers[0]['classes'][0]['class']
                sendMessage = TextSendMessage(text='You don\'t look like any celebrities, but you look like a ' + type_class)
                #call v3/classify with 
                #call v3/detect_face
            # 5 others. send a text message
            else:
                type_class = classifiers[0]['classes'][0]['class']
                app.logger.info('not human but a type_class: ' + type_class)
                text = "Is that a " + type_class + "? If I'm mistaken, please take a clearer picture of yourself."
                sendMessage = TextSendMessage(text=text)
        else:
            continue

        line_bot_api.reply_message(event.reply_token, sendMessage)

    return 'OK'

# Save image to cloudinary 
def saveContentImage(event):
    app.logger.info(str(event))
    message_content = line_bot_api.get_message_content(event.message.id)
    image_binary = message_content.content 

    # save image to cloudinary
    fp = open("temp_img", 'wb') 
    fp.write(image_binary)
    fp.close()
    image_url, image_id = image_management.upload(event.message.id, 'temp_img')

    return image_url

# Classify image in Bluemix
def classifyImageMessage(image_url):
    #initialize v3/classify
    classifier = config.get('DEFAULT', 'Bluemix_Classifier')
    threshold = config.get('DEFAULT', 'Bluemix_Threshold')
    app.logger.info('classifier: ' + classifier)

    #call v3/classify
    response = visual_recognition.classify(
        images_url=image_url,
        classifier_ids=[classifier, 'default'], 
        threshold=threshold
        )
    app.logger.info(json.dumps(response, indent=2))

    # check if a classifier is detected in the image
    if 'classifiers' in json.dumps(response):
        return response['images'][0]['classifiers']
    else:
        return 0

# Create a carouse message template if user looks like a celebrity
def createMessageTemplate(user, classifiers):
    columns = []
    for index, celeb_class in enumerate(classifiers[0]['classes']):
        celeb = celeb_db.findRecordWithId(celeb_class['class'])
        app.logger.info(str(celeb))
        score = computeScore(celeb_class['score'])
        app.logger.info('Carousel index:' + str(index) + ' for ' + str(celeb['en_name']) + ' score: ' + str(score))
        title = user + ' looks like ' + celeb['local_name'] + '(' + celeb['en_name'] + ')'
        temp = CarouselColumn(
            thumbnail_image_url=celeb['image_url'],
            title=title[:40],
            text='Score: ' + score + '%',
            actions=[
                PostbackTemplateAction(
                    label='Agree',
                    text= user + ' looks like ' + celeb['local_name'],
                    data='action=agree&text=' + index
                ),
                MessageTemplateAction(
                    label='Disagree',
                    text='I think ' + user + ' is ' + Compliment.getRandomCompliment(celeb['sex']) + ' than ' + celeb['local_name'] 
                ),
                URITemplateAction(
                    label='Share',
                    uri='http://example.com/1'
                )
            ]
        )
        columns.append(temp)
    
    carousel_template_message = TemplateSendMessage(
        alt_text= user + ' has is a celebrity look alike! Please check your smartphone',
        template=CarouselTemplate(columns=columns)
    )
    return carousel_template_message

# create a welcome message
def createWelcomeMessage(): 
    text_message = TextSendMessage(text=config.get(language, 'Welcome_Message'))
    return text_message

# create a confirm message
def createConfirmMessage():
    confirm_template_message = TemplateSendMessage(
        alt_text='Please check message on your smartphone',
        template=ConfirmTemplate(
            text='Do you want to know which celebrity you look like?',
            actions=[
                PostbackTemplateAction(
                    label='Yes!',
                    text='Yes! Who do I look like?',
                    data='action=tryme'
                ),
                MessageTemplateAction(
                    label='About Me',
                    text='I\'m a bot that searches for a celebrities who look like you. Try and send me a picture!'
                )
            ]
        )
    )
    return confirm_template_message

# compute look alike score of a celebrity
def computeScore(json_score):
    magic_num = 10
    score = (json_score * 100) + magic_num
    if score >= 100:
        score = 99
    return str(round(score, 2))

# analyze postback action
def analyzePostbackEvent(event):
    app.logger.info('postback action: ' + str(event.postback.data))
    if str(event.postback.data) == 'action=tryme':
        app.logger.info('user id: ' + event.user.user_id)
        text_message = TextSendMessage(text='That\'s great ' + event.user.user_id + '! Please send me a picture of yourself.')
    elif str(event.postback.data) == 'action=agree':
        app.logger.info('user id: ' + event.user.user_id)
        text_message = TextSendMessage(text='That\'s great ' + event.user.user_id + '! Please send me a picture of yourself.')
    return text_message

# query stackoverflow
def queryStackOverflow(query):
    query = query[3:]
    url = 'https://api.stackexchange.com/2.2/search/advanced?'
    payload = { 
        'site': 'stackoverflow',
        'views':'200',
        'answers':'1',
        'order':'desc',
        'sort':'relevance',
        'pagesize':'4',
        'q':query,
        'body':query
    }
    response = requests.get(url=url, params=payload)
    data = response.json()
    if data['has_more']:
        columns2 = []
        for index, item in enumerate(data['items']):
            app.logger.info(str(index) + ':' + str(item))
            temp = CarouselColumn(
                thumbnail_image_url='https://cdn.sstatic.net/Sites/stackoverflow/company/img/logos/so/so-icon.png',
                title=item['title'][:36] + '...',
                text='Tags: ' + item['tags'][0] + ', '+ item['tags'][1] ,
                actions=[
                    URITemplateAction(
                        label='Go to Article',
                        uri=item['link']
                    ),
                    PostbackTemplateAction(
                        label='Useful',
                        text='Article ' + str(index) + ' is useful',
                        data='action=buy&itemid=1'
                    ),
                    MessageTemplateAction(
                        label='Not useful',
                        text='Article ' + str(index) + ' is not useful'
                    )
                ]
            )
            columns2.append(temp)
        carousel_template_message = TemplateSendMessage(
            alt_text='Test',
            template=CarouselTemplate(
                columns=columns2
            )
        )
        return carousel_template_message
    else:
        text_message = TextSendMessage(text='Not found. Please try other keywords.')
        return text_message
        
    
def querySearchEngine(data, type):
    index = 0
    app.logger.info("type:" + type) 
    template = ImageSendMessage(
                original_content_url='https://upload.wikimedia.org/wikipedia/commons/b/b4/JPEG_example_JPG_RIP_100.jpg',
                preview_image_url='https://upload.wikimedia.org/wikipedia/commons/b/b4/JPEG_example_JPG_RIP_100.jpg'
                )
    return template


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, host='0.0.0.0', port=int(options.port))
