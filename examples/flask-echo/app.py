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
            response = queryStackOverflow(text_message)            
        # if prefix is @go, check 
        #elif text_message.lower().startswith('@go'):
        #    template = analyzeResponse(response, 'go')
        else:
            continue

        template = analyzeResponse(response, text_message[1:3])
        line_bot_api.reply_message(
            event.reply_token, template
        )

    return 'OK'

def queryStackOverflow(query):
    response = 'OK'
    return response

def sendText(text):
    text_message = TextSendMessage(text=text)

def analyzeResponse(response, type):
    app.logger.info("type:" + type) 
    if type is 'so':
        template = TemplateSendMessage(
            alt_text='Buttons template',
            template=ButtonsTemplate(
                thumbnail_image_url='https://example.com/image.jpg',
                title='Menu',
                text='Please select',
                actions=[
                    PostbackTemplateAction(
                        label='postback',
                        text='postback text',
                        data='action=buy&itemid=1'
                    ),
                    MessageTemplateAction(
                        label='message',
                        text='message text'
                    ),
                    URITemplateAction(
                        label='uri',
                        uri='http://example.com/'
                    )
                ]
            )
        )
    elif type is 'go':
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
