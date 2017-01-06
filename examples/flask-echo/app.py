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
import mongo_db
import image_management 

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
            if classifiers is None:
                sendMessage = TextSendMessage(text='I\'m sorry but your image is out of this world.')
                line_bot_api.reply_message(event.reply_token, sendMessage)
                return

            isCelebrity = len(classifiers) > 1
            if not isCelebrity:
                isPerson = 'person' in classifiers.values()

            app.logger.info('isCelebrity: ' + isCelebrity + ' isPerson:' + isPerson)
            # 2 a celebrity look alike, send a template message carousel
            if isCelebrity:
                sendMessage = createMessageTemplate(classifiers)
            # TODO: 3 a person, call detect_face send a single template message, 
            elif isPerson:
                sendMessage = TextSendMessage(text='You don\'t look like any celebrities')
                #call v3/classify with 
                #call v3/detect_face
            # 4 others. send a text message
            else:
                type_class = classifiers[0]['classes'][0]['class']
                app.logger.info('not human but a type_class: ' + type_class)
                text = "Is that a " + type_class + "? If I'm mistaken, please take a clearer picture of yourself."
                sendMessage = TextSendMessage(text=text)
        else:
            continue

        # For stackoverflow
        #if not isinstance(event, MessageEvent):
        #    continue
        #if not isinstance(event.message, TextMessage):
        #    continue
        #text_message = event.message.text
        # if prefix is @so, check StackOverflow
        #if text_message.lower().startswith('@so'):
        #    sendMessage = queryStackOverflow(text_message)            
        # if prefix is @go, check 
        #elif text_message.lower().startswith('@go'):
        #    # do nothing first
        #    sendMessage = None 
        #else:
        #    continue

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

    # check if celebrity is detected in the image
    if not 'classifers' in response:
        return None
    
    classifiers = response['images'][0]['classifiers']
    return classifiers

def createMessageTemplate(data):

    carousel_template_message = TemplateSendMessage(
        alt_text='Carousel template',
        template=CarouselTemplate(
            columns=[
                CarouselColumn(
                    thumbnail_image_url='https://example.com/item1.jpg',
                    title='this is menu1',
                    text='description1',
                    actions=[
                        PostbackTemplateAction(
                            label='postback1',
                            text='postback text1',
                            data='action=buy&itemid=1'
                        ),
                        MessageTemplateAction(
                            label='message1',
                            text='message text1'
                        ),
                        URITemplateAction(
                            label='uri1',
                            uri='http://example.com/1'
                        )
                    ]
                ),
                CarouselColumn(
                    thumbnail_image_url='https://example.com/item2.jpg',
                    title='this is menu2',
                    text='description2',
                    actions=[
                        PostbackTemplateAction(
                            label='postback2',
                            text='postback text2',
                            data='action=buy&itemid=2'
                        ),
                        MessageTemplateAction(
                            label='message2',
                            text='message text2'
                        ),
                        URITemplateAction(
                            label='uri2',
                            uri='http://example.com/2'
                        )
                    ]
                )
            ]
        )
    )
    return carousel_template_message

def createWelcomeMessage(): 
    text_message = TextSendMessage(text=config.get(language, 'Welcome_Message'))
    return text_message

def createConfirmMessage():
    confirm_template_message = TemplateSendMessage(
        alt_text='Please check message on your smartphone',
        template=ConfirmTemplate(
            text='Do you want to know who you look like?',
            actions=[
                PostbackTemplateAction(
                    label='Yes!',
                    text='Yes!',
                    data='action=y'
                ),
                MessageTemplateAction(
                    label='About Me',
                    text='I\'m a bot that searches for a celebrities who look like you. Try me!'
                )
            ]
        )
    )
    return confirm_template_message

def analyzePostbackEvent(event):
    app.logger.info('postback action: ' + str(event.postback.data))
    if str(event.postback.data) == 'action=y':
        app.logger.info('user id: ' + event.user.user_id)
        text_message = TextSendMessage(text='That\'s great ' + event.user.user_id + '! Please send me a picture of yourself.')
    return text_message

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
