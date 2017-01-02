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
import requests, json
from argparse import ArgumentParser

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, ImageSendMessage,
    ButtonsTemplate, ConfirmTemplate, CarouselTemplate, CarouselColumn, 
    TemplateAction, PostbackTemplateAction, MessageTemplateAction, URITemplateAction
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


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    #app.logger.info("Request body: " + body)
    #app.logger.info("Signature: " + signature)

    # parse webhook body
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(500)

    # if event is MessageEvent and message is TextMessage, then check prefix
    for event in events:
        text_message = event.message.text
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessage):
            continue

        # if prefix is @so, check StackOverflow
        if text_message.lower().startswith('@so'):
            sendMessage = queryStackOverflow(text_message)            
        # if prefix is @go, check 
        elif text_message.lower().startswith('@go'):
            # do nothing first
            sendMessage = None 
        else:
            continue
        a = TemplateSendMessage()
        a = sendMessage
        line_bot_api.reply_message(
            event.reply_token, a
        )

    return 'OK'

def queryStackOverflow(query):
    query = query[3:]
    url = 'https://api.stackexchange.com/2.2/search/advanced?'
    payload = { 
        'site': 'stackoverflow',
        'views':'200',
        'answers':'1',
        'order':'desc',
        'sort':'relevance',
        'pagesize':'5',
        'q':query,
        'body':query
    }
    response = requests.get(url=url, params=payload)
    data = response.json()
    if data['has_more']:
        columns = []
        for index, item in enumerate(data['items']):
            temp = CarouselColumn(
                thumbnail_image_url='https://cdn.sstatic.net/Sites/stackoverflow/company/img/logos/so/so-icon.png?v=c78bd457575a',
                title=item['title'],
                text='Tags:' + json.dumps(item['tags']),
                actions=[
                    URITemplateAction(
                        label='Read Article',
                        uri=item['link']
                    ),
                    URITemplateAction(
                        label='Share',
                        uri='https://lineit.line.me/share/ui?url=' + item['link']
                    )
                ]
            )
            columns.append(temp)
        print columns
        carousel_template_message = TemplateSendMessage(
            alt_text='This message is only available on your smartphone',
            template=CarouselTemplate(columns=columns)
        )
        print carousel_template_message
        return carousel_template_message
    else:
        carousel_template_message = TemplateSendMessage(
            alt_text='Test',
            template=CarouselTemplate(
                columns=[
                    CarouselColumn(
                        thumbnail_image_url='https://example.com/item2.jpg',
                        title='this is menu1',
                        text='Tags',
                        actions=[
                            URITemplateAction(
                                label='uri1',
                                uri='http://example.com/1'
                            ),
                            MessageTemplateAction(
                                label='message1',
                                text='message text'
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
        text_message = TextSendMessage(text='No result found. Please try different keywords?')
        print carousel_template_message
        return carousel_template_message
    
def sendText(text):
    text_message = TextSendMessage(text=text)

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
