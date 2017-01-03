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
from argparse import ArgumentParser

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
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)
locale = configparser.ConfigParser()
locale.read('locale.py')
language = locale['DEFAULT']['language']

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
        text_message = event.message.text
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
        elif isinstance(event, MessageEvent) and isinstance(event.message, ImageMessage)
            # If user sends an image
            sendMessage = analyzeImageMessage(event)
        else:
            continue

        # For stackoverflow
        #if not isinstance(event, MessageEvent):
        #    continue
        #if not isinstance(event.message, TextMessage):
        #    continue
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

def analyzeImageMessage(event):
    

def createWelcomeMessage(): 
    text_message = TextSendMessage(text=locale[language]['Welcome_Message'])
    return text_message

def createConfirmMessage():
    confirm_template_message = TemplateSendMessage(
        alt_text='Please check message on your smartphone',
        template=ConfirmTemplate(
            text='Do you want to know who you look like?',
            actions=[
                PostbackTemplateAction(
                    label='postback',
                    text='Yes!',
                    data='action=y'
                ),
                MessageTemplateAction(
                    label='About Me',
                    text='I\'m a bot that searches for a celebrity who looks like you. Try me!'
                )
            ]
        )
    )
    return confirm_template_message

def analyzePostbackEvent(event):
    print 'postback action: ' + event.postback.data.action
    if event.postback.data.action == 'y':
        print 'user id: ' + event.user.user_id
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
            print str(index) + ':' + str(item)
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
